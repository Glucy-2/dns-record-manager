#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import dns.query
import dns.message
import requests


__author__ = "Glucy2"
BasicDateFormat = "%Y%m%dT%H%M%SZ"
Algorithm = "SDK-HMAC-SHA256"


class server_config:
    dns_query_server: str
    huaweicloud_dns_api = {
        "scheme": "",
        "endpoint": "",
        "access_id": "",
        "access_key": "",
    }


class update_item:
    def __init__(
        self, hostname, enable_ipv4, enable_ipv6, cname_records, ipv4_ips, ipv6_ips
    ):
        self.hostname = hostname
        self.enable_ipv4 = enable_ipv4
        self.enable_ipv6 = enable_ipv6
        self.cname_records = cname_records
        self.ipv4_ips = ipv4_ips
        self.ipv6_ips = ipv6_ips


def read_config():
    f = None
    try:
        f = open("config.json", "r")
        config = json.load(f)
        print("正在读取服务器设置……")
        server_config.dns_query_server = config["server_config"]["dns_query_server"]
        server_config.huaweicloud_dns_api["endpoint"] = config["server_config"][
            "huaweicloud_dns_api"
        ]["endpoint"]
        print("正在读取更新项目……")
        update_items = config["update_items"]
        update_item_list = []
        item_num = 0
        for item in update_items:
            update_item_list.append(
                update_item(
                    item["hostname"],
                    item["enable_ipv4"],
                    item["enable_ipv6"],
                    item["cname_records"],
                    [],
                    [],
                )
            )
            item_num += 1
        print("总共读取了 " + str(item_num) + " 个更新项目")
        return update_item_list

    # except JSONDecodeError:
    #    print("错误：配置文件格式错误")
    #    exit()
    except Exception as e:
        print("错误：" + str(e))
        return []
    finally:
        if f:
            f.close()


def query_ip(cname, record_type, dns_query_server):
    ips = []
    r = dns.query.tcp(dns.message.make_query(cname, record_type), dns_query_server)
    for rr in r.answer:
        for item in rr.items:
            if item.rdtype == 1 and record_type == "A":  # A
                ips.append(item.address)
            elif item.rdtype == 28 and record_type == "AAAA":  # AAAA
                ips.append(item.address)
            elif item.rdtype == 5:  # CNAME
                return query_ip(item.target.to_text(), record_type, dns_query_server)
            else:
                print("未知或错误的记录：" + str(item))
    return ips


def get_zone_id(domain):
    zones = requests.get(server_config.huaweicloud_dns_api["scheme"] + "://" + server_config.huaweicloud_dns_api["endpoint"] + "/v2/zones")


def run():
    print("欢迎使用 multi-cname-dns，本程序由 Glucy2 开发，基于 GPL-3.0 协议开源")
    update_item_list = read_config()
    if update_item_list:
        for one_update_item in update_item_list:
            if one_update_item.enable_ipv4:
                print("正在更新 " + one_update_item.hostname + " 设置的 IPv4 地址……")
                for cname in one_update_item.cname_records:
                    one_update_item.ipv4_ips.extend(
                        query_ip(cname, "A", server_config.dns_query_server)
                    )
                print("IPv4：" + str(one_update_item.ipv4_ips))
            if one_update_item.enable_ipv6:
                print("正在更新 " + one_update_item.hostname + " 设置的 IPv6 地址……")
                for cname in one_update_item.cname_records:
                    one_update_item.ipv6_ips.extend(
                        query_ip(cname, "AAAA", server_config.dns_query_server)
                    )
                print("IPv6：" + str(one_update_item.ipv6_ips))
    else:
        print("错误：更新项目为空")
        exit()


if __name__ == "__main__":
    run()
