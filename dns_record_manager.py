#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import time
import json
import logging
from logging import debug, info, warning, error, critical
import requests
import dns.query
import dns.message
import dns.rdatatype
from hw_apig_sdk import signer
from collections import defaultdict


__author__ = "Glucy2"


class ServerCfg:
    dns_query_server: str = "https://cloudflare-dns.com/dns-query"
    ua: str = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/113.0"
    hw_api: dict = {
        "scheme": "https",
        "endpoint": "dns.myhuaweicloud.com",
        "ak": "",
        "sk": "",
    }
    max_content_num: int = 50
    headers: dict
    sig = signer.Signer()


class UpItem:
    def __init__(self):
        self.name:str = ""
        self.record_type: str = ""
        self.sources: list[str] = []
        self.content: list[str] = []
        self.match_description: str = ""
        self.description: str = ""
        self.ttl: int = 300


def read_config() -> list:
    f = None
    info("正在读取配置文件……")
    try:
        f = open("config.json", "r", encoding="utf-8")
        config = json.load(f)
    except FileNotFoundError:
        critical("错误：找不到配置文件 config.json")
        sys.exit(1)
    except PermissionError:
        critical("错误：无法读取配置文件 config.json")
        sys.exit(1)
    except json.JSONDecodeError as e:
        critical(f"错误：配置文件格式错误，读取失败：{e}")
        sys.exit(1)
    except Exception as e:
        critical(f"错误：读取配置文件失败：{e}")
        sys.exit(1)
    finally:
        if f:
            f.close()
    info("正在读取服务器设置……")
    try:
        ServerCfg.dns_query_server = config["server_config"]["dns_query_server"]
        ServerCfg.ua = config["server_config"]["ua"]
        ServerCfg.hw_api["scheme"] = config["server_config"]["hw_api"]["scheme"]
        ServerCfg.hw_api["endpoint"] = config["server_config"]["hw_api"]["endpoint"]
        ServerCfg.hw_api["ak"] = config["server_config"]["hw_api"]["ak"]
        ServerCfg.hw_api["sk"] = config["server_config"]["hw_api"]["sk"]
        ServerCfg.max_content_num = config["server_config"]["max_content_num"]
    except KeyError as e:
        critical("错误：服务器设置中缺少 " + str(e) + " 配置项")
        sys.exit(1)
    info("正在读取更新配置……")
    up_items = config["update_items"]
    up_item_list = []
    for index, item in enumerate(up_items):
        if not item.get("enabled", True):
            continue
        if not all(item.get(key) for key in ["domain", "type"]):
            error(f"错误：第 {index + 1} 个更新配置缺少必要的配置项")
            continue
        domains = (
            item["domain"] if isinstance(item["domain"], list) else [item["domain"]]
        )
        record_types = (
            item["type"] if isinstance(item["type"], list) else [item["type"]]
        )
        for record_type in record_types:
            if record_type not in {"A", "AAAA", "MX", "TXT", "SRV", "NS", "CAA"}:
                error(f'错误：不支持第 {index + 1} 个更新配置的 {item["type"]} 记录类型')
                continue
        skip = False
        for domain in domains:
            for record_type in record_types:
                up_item = UpItem()
                up_item.name = domain if domain.endswith(".") else domain + "."
                up_item.record_type = record_type
                up_item.sources = item["sources"]
                if record_type == "CAA":
                    content = []
                    for record in item.get("extra", []):
                        sp = record.split(" ")
                        if len(sp) != 3:
                            error(f"错误：第 {index + 1} 个更新配置的 {up_item.name} 的 extra 内容格式错误")
                            skip = True
                            break
                        if sp[2].startswith("\"") and sp[2].endswith("\""):
                            content.append(f"{sp[0]} {sp[1]} {sp[2]}")
                        else:
                            content.append(f"{sp[0]} {sp[1]} \"{sp[2]}\"")
                    up_item.content = content
                else:
                    up_item.content = item.get("extra", [])
                up_item.match_description = item.get("match_description", "")
                up_item.description = item.get(
                    "description", "，".join(item["sources"])
                )[:255]
                up_item.ttl = item.get("ttl", 300)
                if len(up_item.content) > ServerCfg.max_content_num:
                    error(
                        f"错误：第 {index + 1} 个更新配置的 {up_item.name} 的 {up_item.record_type} 设置的额外记录内容数量超过上限 {ServerCfg.max_content_num}"
                    )
                    skip = True
                    break
                up_item_list.append(up_item)
                debug(f"读取到更新项目：{up_item.__dict__}")
            if skip:
                break
    if up_item_list:
        info(f"总共读取了 {len(up_item_list)} 个更新项目")
        return up_item_list
    else:
        critical("错误：没有可用的更新项目")
        sys.exit(1)


def query_record(
    name: str,
    record_type: str,
    lookup_session: requests.sessions.Session,
) -> list:
    content = []
    r = dns.query.https(
        dns.message.make_query(name, record_type),
        where=ServerCfg.dns_query_server,
        session=lookup_session,
    )
    try:
        rdatatype = dns.rdatatype.from_text(record_type)
    except dns.rdatatype.UnknownRdatatype:
        error(f"未知或错误的记录类型：{record_type}")
        return content
    for rr in r.answer:
        for item in rr.items:
            if item.rdtype == dns.rdatatype.CNAME:
                debug(f"查询到 {name} 的 CNAME 记录：{item.target.to_text()}")
                return query_record(item.target.to_text(), record_type, lookup_session)
            elif item.rdtype == rdatatype:
                if record_type == "CAA":
                    content.append(f"{item.flags} {item.tag.decode()} \"{item.value.decode()}\"")
                elif record_type == "NS":
                    content.append(str(item.target))
                elif record_type == "MX":
                    content.append(str(item.exchange))
                elif record_type == "TXT":
                    for string in item.strings:
                        content.append(string.decode())
                else:
                    content.append(item.address)
            else:
                error(f"未知或错误的记录：{item}")
    debug(f"查询到 {name} 的 {record_type} 记录：{content}")
    return content


def get_asn(ip: str, s: requests.sessions.Session, wait: bool = True) -> int:
    r = s.get(f"https://api.ip.sb/geoip/{ip}")
    if r.status_code == 200:
        try:
            return r.json()["asn"]
        except requests.JSONDecodeError as e:
            error(f"获取 {ip} 的 ASN 失败：{e}")
            return 0
        except KeyError as e:
            error(f"获取 {ip} 的 ASN 失败：{e}")
            return 0
    elif r.status_code == 429 and wait:
        warning(f"获取 {ip} 的 ASN 时超出速率限制：{r.status_code} {r.text}，等待 60 秒后重试……")
        time.sleep(60)
        return get_asn(ip, s, True)
    else:
        error(f"获取 {ip} 的 ASN 失败：{r.status_code} {r.text}")
        return 0


def query_records(
    names: list,
    record_type: str,
    session: requests.sessions.Session,
    domain: str = "",
    extra_num: int = 0,
) -> list[str]:
    contents = []
    for name in names:
        contents.append(query_record(name, record_type, session))
    debug(f"{domain} 查询到的记录：{contents}")
    total_num = sum(len(content) for content in contents)
    if total_num + extra_num > ServerCfg.max_content_num:
        warning(
            f"{domain} 的记录数 {total_num + extra_num} 超过了设置的最大记录数 {ServerCfg.max_content_num}"
        )
        if record_type in {"A", "AAAA"}:
            record_by_asn = defaultdict(list)
            for content in contents:
                for record in content:
                    record_by_asn[get_asn(record, session)].append(record)
            contents = sorted(record_by_asn.values(), key=len, reverse=True)
        while total_num + extra_num > ServerCfg.max_content_num:
            contents.sort(key=len, reverse=True)
            if not contents:
                break
            contents[0].pop()
            total_num -= 1
        debug(f"{domain} 查询到的记录（截断后）：{contents}")
    records = []
    for content in contents:
        records.extend(content)
    return records


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
            sys.exit(1)


def hwapi_requester(method: str, url: str, body: str = "") -> requests.Response:
    r = signer.HttpRequest(method, url, body=body)
    ServerCfg.sig.Sign(r)
    return requests.request(
        r.method, r.scheme + "://" + r.host + r.uri, headers=r.headers, data=r.body
    )


def get_zones() -> list:
    info("正在查询 Zone 列表……")
    zone_list_r = hwapi_requester(
        "GET",
        ServerCfg.hw_api["scheme"] + "://" + ServerCfg.hw_api["endpoint"] + "/v2/zones",
    )
    zone_list_j = zone_list_r.json()
    if zone_list_r.status_code != 200:
        critical(f'错误：查询 Zone 列表失败，错误信息：{zone_list_j["error_msg"]}')
        sys.exit(1)
    zones: list = zone_list_j["zones"]
    while "next" in zone_list_j["links"]:
        zone_list_r = hwapi_requester("GET", zone_list_j["links"]["next"])
        zones.extend(zone_list_j["zones"])
    zone_msg = "，".join(f'{zone["name"]}：{zone["id"]}' for zone in zones)
    debug(f"查询到 {len(zones)} 个 Zone：{zone_msg}")
    return zones


def get_recordset_list(zones: list, up_item: UpItem) -> tuple[str, dict] | None:
    # 切割域名，获取主域名和对应 Zone ID
    for zone in zones:
        if up_item.name.endswith(zone["name"]):
            zone_name = zone["name"]
            zone_id = zone["id"]
            info(f"找到了 {up_item.name} 对应的主域名：{zone_name}，对应的 Zone ID：{zone_id}")
            break
    else:
        error(f"错误：未找到 {up_item.name} 对应的主域名，请检查配置文件中的 domain 的主域名是否已添加到华为云 DNS 的公网域名")
        return None

    # 获取 Zone 下的记录列表
    info(f"正在查询 {zone_name} 下的记录列表……")
    record_sets_r = hwapi_requester(
        "GET",
        f'{ServerCfg.hw_api["scheme"]}://{ServerCfg.hw_api["endpoint"]}/v2/zones/{zone_id}/recordsets',
    )
    record_sets_j = record_sets_r.json()
    if record_sets_r.status_code != 200:
        error(f'错误：查询记录列表失败，错误信息：{record_sets_j["message"]}')
        return None
    recordsets: list = record_sets_j["recordsets"]
    while "next" in record_sets_j["links"]:
        record_sets_r = hwapi_requester("GET", record_sets_j["links"]["next"])
        recordsets.append(record_sets_j["recordsets"])
    recordset_list = []
    for recordset in recordsets:
        if (
            recordset["name"] == up_item.name
            and recordset["type"] == up_item.record_type
        ):
            recordset_list.append(recordset)
    return zone_id, recordset_list


def update_recordset(zone_id: str, recordset: dict, up_item: UpItem) -> bool:
    update_record_r = hwapi_requester(
        "PUT",
        f'{ServerCfg.hw_api["scheme"]}://{ServerCfg.hw_api["endpoint"]}/v2/zones/{zone_id}/recordsets/{recordset["id"]}',
        json.dumps(
            {
                "name": up_item.name,
                "type": up_item.record_type,
                "records": up_item.content,
                "description": up_item.description,
                "ttl": up_item.ttl,
            }
        ),
    )
    update_record_j = update_record_r.json()
    if update_record_r.status_code == 202:
        info(
            f'{up_item.name} 的 {up_item.record_type} 记录更新成功，记录已更新为 {update_record_j["records"]}'
        )
        return True
    else:
        error(
            f"错误：{up_item.name} 的 {up_item.record_type} 记录更新失败，错误信息：{update_record_j['message']}"
        )
        return False


def query_recordset(zone_id: str, recordset_id: str) -> dict:
    debug(f"正在查询 Zone {zone_id} 中的 {recordset_id} 的记录集……")
    query_record_r = hwapi_requester(
        "GET",
        f'{ServerCfg.hw_api["scheme"]}://{ServerCfg.hw_api["endpoint"]}/v2.1/zones/{zone_id}/recordsets/{recordset_id}',
    )
    query_record_j = query_record_r.json()
    if query_record_r.status_code == 200:
        debug(f"查询 Zone {zone_id} 中的 {recordset_id} 的记录集成功：{query_record_j}")
        return query_record_j
    else:
        error(
            f"查询 Zone {zone_id} 中的 {recordset_id} 的记录集失败，错误信息：{query_record_j['message']}"
        )
        return {}


def add_recordset(zone_id: str, up_item: UpItem) -> bool:
    add_record_r = hwapi_requester(
        "POST",
        f'{ServerCfg.hw_api["scheme"]}://{ServerCfg.hw_api["endpoint"]}/v2.1/zones/{zone_id}/recordsets',
        json.dumps(
            {
                "name": up_item.name,
                "type": up_item.record_type,
                "records": up_item.content,
                "description": up_item.description,
                "ttl": up_item.ttl,
            }
        ),
    )
    add_record_j = add_record_r.json()
    if add_record_r.status_code in {200, 202}:
        debug(
            f'{up_item.name} 的 {up_item.record_type} 记录集添加成功，记录集已添加为 {add_record_j["records"]}'
        )
        return True
    else:
        error(
            f"错误：{up_item.name} 的 {up_item.record_type} 记录集添加失败，错误信息：{add_record_j['message']}"
        )
        return False


def set_recordset_status(recordset_id: str, status: str = "DISABLE") -> bool:
    if status not in {"DISABLE", "ENABLE"}:
        error(f"错误：无效记录集的状态：{status}")
        return False
    set_status_r = hwapi_requester(
        "PUT",
        f'{ServerCfg.hw_api["scheme"]}://{ServerCfg.hw_api["endpoint"]}/v2.1/recordsets/{recordset_id}/statuses/set',
        json.dumps({"status": status}),
    )
    set_status_j = set_status_r.json()
    if set_status_r.status_code == 200:
        debug(f"记录集 {recordset_id} 的状态成功更改为 {set_status_j['status']}")
        return True
    else:
        error(f"错误：记录集 {recordset_id} 的状态更改失败，错误信息：{set_status_j['message']}")
        return False


def run():
    if sys.gettrace():
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(
        format="[%(asctime)s][%(process)d][%(funcName)s (%(filename)s:%(lineno)d)]: [%(levelname)s]: %(message)s",
        level=log_level,
    )
    info("欢迎使用 dns-record-manager，基于 GPL-3.0 协议开源")
    up_item_list: list[UpItem] = read_config()
    setup_signer()
    zones = get_zones()
    with requests.sessions.Session() as lookup_session:
        lookup_session.headers = {"User-Agent": ServerCfg.ua}
        for up_item in up_item_list:
            # 查询 源记录 中的 值
            info(f"正在查询 {up_item.name} 设置的 {up_item.record_type} 记录……")
            up_item.content.extend(
                query_records(
                    up_item.sources,
                    up_item.record_type,
                    lookup_session,
                    up_item.name,
                    len(up_item.content),
                )
            )
            recordset_list = get_recordset_list(zones, up_item)
            if recordset_list is None:
                continue
            else:
                zone_id, recordsets = recordset_list
            if not recordsets:
                if up_item.content:
                    info(f"正在添加 {up_item.name} 设置的 {up_item.record_type} 记录……")
                    add_recordset(zone_id, up_item)
                    continue
                else:
                    warning(f"{up_item.name} 没有 {up_item.record_type} 记录需要更新、禁用或添加")
                    continue
            for recordset in recordsets:
                debug(f"正在处理 {up_item.name} 的 {recordset['id']} 记录集……")
                query_recordset_result = query_recordset(zone_id, recordset["id"])
                if query_recordset_result["description"] is None:
                    query_recordset_result["description"] = ""
                if query_recordset_result["description"] == up_item.description and set(
                    query_recordset_result["records"]
                ) == set(up_item.content):
                    info(f"{up_item.name} 的 {query_recordset_result['id']} 记录集没有变化，将跳过")
                    continue
                if query_recordset_result["status"] != "ACTIVE":
                    info(
                        f"{up_item.name} 的 {query_recordset_result['id']} 记录集状态为 {query_recordset_result['status']}，将跳过"
                    )
                    continue
                if up_item.match_description and not re.search(
                    up_item.match_description,
                    (query_recordset_result["description"])
                ):
                    info(
                        f"{up_item.name} 的 {query_recordset_result['id']} 记录集描述不匹配，将跳过"
                    )
                    continue
                if up_item.content:
                    info(f"正在更新 {up_item.name} 的 {up_item.record_type} 记录……")
                    update_recordset(zone_id, recordset, up_item)
                else:
                    info(f"{up_item.name} 要设置的 {up_item.record_type} 记录集为空，将禁用现有记录集……")
                    set_recordset_status(recordset["id"], "DISABLE")


if __name__ == "__main__":
    run()
