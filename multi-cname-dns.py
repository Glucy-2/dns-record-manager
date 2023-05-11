#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import logging
from logging import debug, info, warning, error, critical
import dns.query
import dns.message
from hw_apig_sdk import signer
import requests


__author__ = "Glucy2"


class ServerCfg:
    dns_query_server: str
    hw_api = {
        "scheme": "",
        "endpoint": "",
        "ak": "",
        "sk": "",
    }
    headers: dict
    sig = signer.Signer()


class UpItem:
    def __init__(
        self,
        hostname,
        enable_ipv4,
        enable_ipv6,
        cname_records,
        ipv4_ips,
        ipv6_ips,
        description,
        ttl,
    ):
        self.hostname = hostname
        self.enable_ipv4 = enable_ipv4
        self.enable_ipv6 = enable_ipv6
        self.cname_records = cname_records
        self.ipv4_ips = ipv4_ips
        self.ipv6_ips = ipv6_ips
        self.description = description
        self.ttl = ttl


def read_config() -> list:
    f = None
    try:
        f = open("config.json", "r")
        config = json.load(f)
        info("正在读取服务器设置……")
        ServerCfg.dns_query_server = config["server_config"]["dns_query_server"]
        ServerCfg.hw_api["scheme"] = config["server_config"]["hw_api"]["scheme"]
        ServerCfg.hw_api["endpoint"] = config["server_config"]["hw_api"]["endpoint"]
        ServerCfg.hw_api["ak"] = config["server_config"]["hw_api"]["ak"]
        ServerCfg.hw_api["sk"] = config["server_config"]["hw_api"]["sk"]
        info("正在读取更新项目……")
        up_items = config["update_items"]
        up_item_list = []
        for item in up_items:
            up_item_list.append(
                UpItem(
                    item["hostname"],
                    item["enable_ipv4"],
                    item["enable_ipv6"],
                    item["cname_records"],
                    item["ipv4_ips"],
                    item["ipv6_ips"],
                    item["description"],
                    item["ttl"],
                )
            )
        info("总共读取了 " + str(len(up_item_list)) + " 个更新项目")
        return up_item_list

    except json.JSONDecodeError:
        error("错误：配置文件格式错误")
        exit()
    except Exception as e:
        error("错误：" + str(e))
        return []
    finally:
        if f:
            f.close()


def query_ip(
    cname: str,
    record_type: str,
    dns_query_server: str,
    lookup_session: requests.sessions.Session,
) -> list:
    ips = []
    cname += "" if cname.endswith(".") else "."
    r = dns.query.https(
        dns.message.make_query(cname, record_type),
        where=dns_query_server,
        session=lookup_session,
    )
    for rr in r.answer:
        for item in rr.items:
            if item.rdtype == 1 and record_type == "A":  # A
                ips.append(item.address)
            elif item.rdtype == 28 and record_type == "AAAA":  # AAAA
                ips.append(item.address)
            elif item.rdtype == 5:  # CNAME
                return query_ip(
                    item.target.to_text(), record_type, dns_query_server, lookup_session
                )
            else:
                error("未知或错误的记录：" + str(item))
    return ips


def setup_signer():
    ServerCfg.headers = {"Content-Type": "application/json"}
    ServerCfg.sig.Key = os.getenv("HW_API_KEY")
    ServerCfg.sig.Secret = os.getenv("HW_API_SECRET")
    if ServerCfg.sig.Key and ServerCfg.sig.Secret:
        info("检测到环境变量 HW_API_KEY 和 HW_API_SECRET，将使用环境变量中的凭证")
    else:
        ServerCfg.sig.Key = ServerCfg.hw_api["ak"]
        ServerCfg.sig.Secret = ServerCfg.hw_api["sk"]
        if ServerCfg.sig.Key and ServerCfg.sig.Secret:
            info("检测到配置文件中的凭证，将使用配置文件中的凭证")
        else:
            critical("错误：未找到凭证")
            exit()


def hwapi_requester(method: str, url: str, body: str = "") -> requests.Response:
    r = signer.HttpRequest(method, url, body=body)
    ServerCfg.sig.Sign(r)
    return requests.request(
        r.method, r.scheme + "://" + r.host + r.uri, headers=r.headers, data=r.body
    )


def run():
    if sys.gettrace():
        logging.basicConfig(
            format="[%(asctime)s][%(process)d][%(funcName)s (%(filename)s:%(lineno)d)]: [%(levelname)s]: %(message)s",
            level=logging.DEBUG,
        )
    else:
        logging.basicConfig(
            format="[%(asctime)s][%(process)d][%(funcName)s (%(filename)s:%(lineno)d)]: [%(levelname)s]: %(message)s",
            level=logging.INFO,
        )
    info("欢迎使用 multi-cname-dns，本程序由 Glucy2 开发，基于 GPL-3.0 协议开源")
    up_item_list = read_config()
    setup_signer()
    if up_item_list:
        # 查询 Zone 列表
        info("正在查询 Zone 列表……")
        zone_list_r = hwapi_requester(
            "GET",
            ServerCfg.hw_api["scheme"]
            + "://"
            + ServerCfg.hw_api["endpoint"]
            + "/v2/zones",
        )
        zone_list_j = zone_list_r.json()
        if zone_list_r.status_code != 200:
            critical("错误：查询 Zone 列表失败，错误信息：" + str(zone_list_j["error_msg"]))
            return
        zones = zone_list_j["zones"]
        while "next" in zone_list_j["links"]:
            zone_list_r = hwapi_requester("GET", zone_list_j["links"]["next"])
            zones.append(zone_list_j["zones"])

        with requests.sessions.Session() as lookup_session:
            for one_up_item in up_item_list:
                # 查询 CNAME 中的 IP
                if one_up_item.enable_ipv4:
                    info("正在查询 " + one_up_item.hostname + " 设置的 IPv4 地址……")
                    for cname in one_up_item.cname_records:
                        one_up_item.ipv4_ips.extend(
                            query_ip(
                                cname, "A", ServerCfg.dns_query_server, lookup_session
                            )
                        )
                    info(
                        one_up_item.hostname
                        + " 设置的 IPv4 地址："
                        + str(one_up_item.ipv4_ips)
                    )
                if one_up_item.enable_ipv6:
                    info("正在查询 " + one_up_item.hostname + " 设置的 IPv6 地址……")
                    for cname in one_up_item.cname_records:
                        one_up_item.ipv6_ips.extend(
                            query_ip(
                                cname,
                                "AAAA",
                                ServerCfg.dns_query_server,
                                lookup_session,
                            )
                        )
                    info(
                        one_up_item.hostname
                        + " 设置的 IPv6 地址："
                        + str(one_up_item.ipv6_ips)
                    )

                # 切割域名，获取主域名和对应 Zone ID
                for zone in zones:
                    domain = (
                        one_up_item.hostname
                        if one_up_item.hostname.endswith(".")
                        else one_up_item.hostname + "."
                    )
                    if domain.endswith(zone["name"]):
                        zone_name = zone["name"]
                        zone_id = zone["id"]
                        info(
                            "找到了 "
                            + one_up_item.hostname
                            + " 对应的主域名："
                            + zone_name
                            + "，对应的 Zone ID："
                            + zone_id
                        )
                        break
                else:
                    error(
                        "错误：未找到 "
                        + one_up_item.hostname
                        + " 对应的主域名。请检查配置文件中的 hostname 以及 ak 与 sk 对应的账号是否正确"
                    )

                # 获取 Zone 下的记录列表
                info("正在查询 " + zone_name + " 下的记录列表……")
                record_sets_r = hwapi_requester(
                    "GET",
                    ServerCfg.hw_api["scheme"]
                    + "://"
                    + ServerCfg.hw_api["endpoint"]
                    + "/v2/zones/"
                    + zone_id
                    + "/recordsets",
                )
                record_sets_j = record_sets_r.json()
                if record_sets_r.status_code != 200:
                    critical("错误：查询记录列表失败，错误信息：" + str(record_sets_j["message"]))
                    break
                recordsets = record_sets_j["recordsets"]
                while "next" in record_sets_j["links"]:
                    record_sets_r = hwapi_requester(
                        "GET", record_sets_j["links"]["next"]
                    )
                    recordsets.append(record_sets_j["recordsets"])

                # 更新记录
                ipv4_done = False
                ipv6_done = False
                for recordset in recordsets:
                    if recordset["name"] == domain:
                        if recordset["type"] == "A":
                            if one_up_item.ipv4_ips:
                                info("正在更新 " + one_up_item.hostname + " 设置的 IPv4 地址……")
                                update_record_r = hwapi_requester(
                                    "PUT",
                                    ServerCfg.hw_api["scheme"]
                                    + "://"
                                    + ServerCfg.hw_api["endpoint"]
                                    + "/v2/zones/"
                                    + zone_id
                                    + "/recordsets/"
                                    + recordset["id"],
                                    json.dumps(
                                        {
                                            "name": domain,
                                            "type": "A",
                                            "records": one_up_item.ipv4_ips,
                                            "description": one_up_item.description,
                                            "ttl": one_up_item.ttl,
                                        }
                                    ),
                                )
                                update_record_j = update_record_r.json()
                                if update_record_r.status_code == 202:
                                    info(
                                        one_up_item.hostname
                                        + "的 IPv4 更新成功，记录已更新为 "
                                        + str(update_record_j["records"])
                                    )
                                else:
                                    error(
                                        "错误："
                                        + one_up_item.hostname
                                        + "的更新记录失败，错误信息："
                                        + str(update_record_j["message"])
                                    )
                            else:
                                info(one_up_item.hostname + "要设置的 IPv4 地址为空，将删除记录集")
                                del_record_r = hwapi_requester(
                                    "DELETE",
                                    ServerCfg.hw_api["scheme"]
                                    + "://"
                                    + ServerCfg.hw_api["endpoint"]
                                    + "/v2/zones/"
                                    + zone_id
                                    + "/recordsets/"
                                    + recordset["id"],
                                )
                                del_record_j = del_record_r.json()
                                if del_record_r.status_code == 202:
                                    info("删除成功")
                                else:
                                    error(
                                        "错误："
                                        + one_up_item.hostname
                                        + "的 IPv4 地址删除记录失败，错误信息："
                                        + str(del_record_j["message"])
                                    )
                            ipv4_done = True
                        elif recordset["type"] == "AAAA":
                            if one_up_item.ipv6_ips:
                                info("正在更新 " + one_up_item.hostname + " 设置的 IPv6 地址……")
                                update_record_r = hwapi_requester(
                                    "PUT",
                                    ServerCfg.hw_api["scheme"]
                                    + "://"
                                    + ServerCfg.hw_api["endpoint"]
                                    + "/v2/zones/"
                                    + zone_id
                                    + "/recordsets/"
                                    + recordset["id"],
                                    json.dumps(
                                        {
                                            "name": domain,
                                            "type": "AAAA",
                                            "records": one_up_item.ipv6_ips,
                                            "description": one_up_item.description,
                                            "ttl": one_up_item.ttl,
                                        }
                                    ),
                                )
                                update_record_j = update_record_r.json()
                                if update_record_r.status_code == 202:
                                    info(
                                        one_up_item.hostname
                                        + "的 IPv6 更新成功，记录已更新为 "
                                        + str(update_record_j["records"])
                                    )
                                else:
                                    error(
                                        "错误："
                                        + one_up_item.hostname
                                        + "的 IPv6 更新记录失败，错误信息："
                                        + str(update_record_j["message"])
                                    )
                            else:
                                info(one_up_item.hostname + "要设置的 IPv6 地址为空，将删除记录集")
                                del_record_r = hwapi_requester(
                                    "DELETE",
                                    ServerCfg.hw_api["scheme"]
                                    + "://"
                                    + ServerCfg.hw_api["endpoint"]
                                    + "/v2/zones/"
                                    + zone_id
                                    + "/recordsets/"
                                    + recordset["id"],
                                )
                                del_record_j = del_record_r.json()
                                if del_record_r.status_code == 202:
                                    info(one_up_item.hostname + "的 IPv6 记录删除成功")
                                else:
                                    error(
                                        "错误："
                                        + one_up_item.hostname
                                        + "的 IPv6 删除记录失败，错误信息："
                                        + str(del_record_j["message"])
                                    )
                            ipv6_done = True
                if not ipv4_done and one_up_item.ipv4_ips:
                    info("正在添加 " + one_up_item.hostname + " 设置的 IPv4 地址……")
                    add_record_r = hwapi_requester(
                        "POST",
                        ServerCfg.hw_api["scheme"]
                        + "://"
                        + ServerCfg.hw_api["endpoint"]
                        + "/v2/zones/"
                        + zone_id
                        + "/recordsets",
                        json.dumps(
                            {
                                "name": domain,
                                "type": "A",
                                "records": one_up_item.ipv4_ips,
                                "description": one_up_item.description,
                                "ttl": one_up_item.ttl,
                            }
                        ),
                    )
                    add_record_j = add_record_r.json()
                    if add_record_r.status_code == 202:
                        info(
                            one_up_item.hostname
                            + " 的 IPv4 地址添加成功，记录已添加为 "
                            + str(add_record_j["records"])
                        )
                    else:
                        error(
                            "错误："
                            + one_up_item.hostname
                            + " 的 IPv4 地址添加记录失败，错误信息："
                            + str(add_record_j["message"])
                        )
                else:
                    warning(one_up_item.hostname + "没有 IPv4 地址记录需要更新、删除或添加")
                if not ipv6_done and one_up_item.ipv6_ips:
                    info("正在添加 " + one_up_item.hostname + " 设置的 IPv6 地址……")
                    add_record_r = hwapi_requester(
                        "POST",
                        ServerCfg.hw_api["scheme"]
                        + "://"
                        + ServerCfg.hw_api["endpoint"]
                        + "/v2/zones/"
                        + zone_id
                        + "/recordsets",
                        json.dumps(
                            {
                                "name": domain,
                                "type": "AAAA",
                                "records": one_up_item.ipv6_ips,
                                "description": one_up_item.description,
                                "ttl": one_up_item.ttl,
                            }
                        ),
                    )
                    add_record_j = add_record_r.json()
                    if add_record_r.status_code == 202:
                        info(
                            one_up_item.hostname
                            + " 的 IPv6 地址添加成功，记录已添加为 "
                            + str(add_record_j["records"])
                        )
                    else:
                        error(
                            "错误："
                            + one_up_item.hostname
                            + " 的 IPv6 地址添加记录失败，错误信息："
                            + str(add_record_j["message"])
                        )
                else:
                    warning(one_up_item.hostname + "没有 IPv6 地址记录需要更新、删除或添加")
    else:
        error("错误：更新项目为空")
        exit()


if __name__ == "__main__":
    run()
