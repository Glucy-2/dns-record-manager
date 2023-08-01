#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os
import re
import sys
import json
import yaml
import random
import asyncio
import aiohttp
import zipfile
import logging
from logging import debug, info, warning, error, critical
import ipaddress
from collections import defaultdict
from huaweicloudsdkdns.v2 import *
from huaweicloudsdkdns.v2.region import dns_region
from huaweicloudsdkcore.region.region import Region
from huaweicloudsdkcore.exceptions.exceptions import *
from huaweicloudsdkcore.http.http_handler import HttpHandler
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.auth.provider import EnvCredentialProvider


__author__ = "Glucy2"


dns_types = {
    "A": 1,
    "AAAA": 28,
    "AFSDB": 18,
    "APL": 42,
    "CAA": 257,
    "CDNSKEY": 60,
    "CDS": 59,
    "CERT": 37,
    "CNAME": 5,
    "DHCID": 49,
    "DLV": 32769,
    "DNAME": 39,
    "DNSKEY": 48,
    "DS": 43,
    "HIP": 55,
    "HTTPS": 65,
    "IPSECKEY": 45,
    "KEY": 25,
    "LOC": 29,
    "MX": 15,
    "NAPTR": 35,
    "NS": 2,
    "NSEC": 47,
    "NSEC3": 50,
    "NSEC3PARAM": 51,
    "OPENPGPKEY": 61,
    "PTR": 12,
    "RRSIG": 46,
    "RP": 17,
    "SIG": 24,
    "SOA": 6,
    "SPF": 99,
    "SRV": 33,
    "SSHFP": 44,
    "TA": 32768,
    "TKEY": 249,
    "TSIG": 250,
    "TXT": 16,
    "URI": 256,
}


class ServerCfg:
    error_occurred: bool = False
    dns_query_server: str = "https://cloudflare-dns.com/dns-query"
    hw_api_ak: str = ""
    hw_api_sk: str = ""
    ip_lists_urls: list[str] = (
        [
            "https://github.com/gaoyifan/china-operator-ip/archive/refs/heads/ip-lists.zip",
            "https://ghproxy.com/https://github.com/gaoyifan/china-operator-ip/archive/refs/heads/ip-lists.zip",
        ],
    )
    ip_lists_filepath: str = "./ip-lists.zip"
    ip_lists: dict = {}
    headers: dict
    max_content_num: int = 50
    credentials: BasicCredentials


class UpItem:
    def __init__(
        self,
        name: str,
        record_type: str,
        sources: list[str],
        content: list[str],
        match_description: str,
        description: str,
        ttl: int,
    ):
        self.name: str = name
        self.record_type: str = record_type
        self.sources: list[str] = sources
        self.content: list[str] = content
        self.match_description: str = match_description
        self.description: str = description
        self.ttl: int = ttl


def response_handler(**kwargs):
    response = kwargs.get("response")
    request = response.request
    info = f"> Request {request.method} {request.path_url} \n"
    if len(request.headers) != 0:
        info += "> Headers:\n"
        for each in request.headers:
            info += f"    {each}: {request.headers[each]}\n"
    info += f"> Body: {request.body}\n\n"

    info += f"< Response {response.status_code} \n"
    if len(response.headers) != 0:
        info += "< Headers:\n"
        for each in response.headers:
            info += f"    {each}: {response.headers[each]}\n"
    info += f"< Body: {response.content}"
    debug(info)


async def read_config() -> list:
    f = None
    info("正在读取配置文件……")
    try:
        f = open("dns_record_updater.yaml", "r", encoding="utf-8")
        config = yaml.load(f, Loader=yaml.FullLoader)
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
        ServerCfg.hw_api_ak = config["server_config"]["hw_api_ak"]
        ServerCfg.hw_api_sk = config["server_config"]["hw_api_sk"]
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
                name = domain if domain.endswith(".") else domain + "."
                if record_type == "CAA":
                    content = []
                    for record in item.get("extra", []):
                        sp = record.split(" ")
                        if len(sp) != 3:
                            error(f"错误：第 {index + 1} 个更新配置的 {name} 的 extra 内容格式错误")
                            skip = True
                            break
                        if sp[2].startswith('"') and sp[2].endswith('"'):
                            content.append(f"{sp[0]} {sp[1]} {sp[2]}")
                        else:
                            content.append(f'{sp[0]} {sp[1]} "{sp[2]}"')
                    content.extend(content)
                else:
                    if item.get("extra", []):
                        content = item.get("extra", []).copy()
                    else:
                        content = []
                if len(content) > ServerCfg.max_content_num:
                    ServerCfg.error_occurred = True
                    error(
                        f"错误：第 {index + 1} 个更新配置的 {name} 的 {record_type} 设置的额外记录内容数量超过上限 {ServerCfg.max_content_num}"
                    )
                    skip = True
                    break
                if item.get("description"):
                    description = item.get("description", "，".join(item["sources"]))[
                        :255
                    ]
                elif item["sources"]:
                    description = "，".join(item["sources"])
                else:
                    description = ""
                up_item = UpItem(
                    name,
                    record_type,
                    item["sources"],
                    content,
                    item.get("match_description", ""),
                    description,
                    item.get("ttl", 300),
                )
                up_item_list.append(up_item)
                debug(f"读取到更新项目：{name} {record_type}")
                debug(id(content))
            if skip:
                break
    if up_item_list:
        info(f"总共读取了 {len(up_item_list)} 个更新项目")
        return up_item_list
    else:
        critical("错误：没有可用的更新项目")
        sys.exit(1)


async def fetch_url2time(
    session: aiohttp.ClientSession, name: str, url: str, regions: dict
):
    try:
        start_time = asyncio.get_event_loop().time()
        await session.get(url, timeout=5)
        end_time = asyncio.get_event_loop().time()
        regions[name] = end_time - start_time
        debug(f"{name} 的延迟：{regions[name]} 秒")
    except Exception as e:
        debug(f"测试 {name} 的响应时间时出错：{e}")
        return


async def select_region(session: aiohttp.ClientSession) -> list:
    """
    选择延迟最低的 API 服务器
    """
    regions = {}
    info("正在选择响应时间最短的 API 服务器……")
    await asyncio.gather(
        *[
            fetch_url2time(session, name, region.endpoints[0], regions)
            for name, region in dns_region.DnsRegion.static_fields.items()
        ]
    )
    return sorted(regions, key=regions.get)


async def download_ip_lists(session: aiohttp.ClientSession):
    """
    下载 IP 地址数据包
    """
    info("正在下载 IP 地址数据包……")
    f = open(ServerCfg.ip_lists_filepath, "wb")
    for addr in ServerCfg.ip_lists_urls:
        try:
            f.write(await session.get(addr).content.read())
            break
        except Exception as e:
            warning(f"下载 {addr} 时出错：{e}")
            continue


async def load_ip_org(session: aiohttp.ClientSession):
    """
    解压、加载 IP 地址数据
    """
    if not os.path.isfile(ServerCfg.ip_lists_filepath):
        # IP 地址数据包不存在，下载
        await download_ip_lists(session)
    try:
        f = zipfile.ZipFile(ServerCfg.ip_lists_filepath)
        for filename in f.namelist():
            if filename.endswith(".txt"):
                ServerCfg.ip_lists[filename[:-4]] = (
                    f.read(filename).decode().splitlines()
                )
    except zipfile.BadZipFile as e:
        error(f"解压 IP 地址数据包时出错：{e}，尝试重新下载")
    if f:
        f.close()


async def get_ip_org(ip: str, orgs: dict) -> str:
    """
    获取 IP 所在运营商
    """
    ip = ipaddress.ip_address(ip)
    for org in ServerCfg.ip_lists.keys():
        for cidr in ServerCfg.ip_lists[org]:
            if ip in ipaddress.ip_network(cidr):
                debug(f"{ip} 的运营商：{org}")
                return org
    else:
        return "other"


async def choose_ips(num: int, org: str) -> list[str]:
    """
    从指定的已加载的 IP 地址数据中随机选择指定数量的 IP 地址
    """
    all_ip: list = []
    try:
        for cidr in ServerCfg.ip_lists[org]:
            ip_network = ipaddress.ip_network(cidr)
            for ip in ip_network:
                all_ip.append(str(ip))
        return random.sample(all_ip, num)
    except KeyError:
        error(f"错误：未知的 IP 地址数据库：{org}")
        return []


async def lookup_record(
    session: aiohttp.ClientSession,
    name: str,
    record_type: str,
) -> list:
    content = []
    try:
        response: aiohttp.ClientResponse = await session.get(
            ServerCfg.dns_query_server,
            params={"name": name, "type": record_type},
            headers={"Accept": "application/dns-json"},
        )
        if response.status == 200:
            response_json = await response.json(content_type=None)
            for answer in response_json["Answer"]:
                if answer["type"] == dns_types[record_type]:
                    content.append(answer["data"])
        else:
            warning(
                f"查询 {name} {record_type} 记录时出错：{response.status}: {response.content}"
            )
    except Exception as e:
        warning(f"查询 {name} {record_type} 记录时出错：{e}")
    return content


async def lookup_records(
    names: list,
    record_type: str,
    session: aiohttp.ClientSession,
    domain: str = "",
    extra_num: int = 0,
) -> list[str]:
    contents = []
    for name in names:
        contents.append(await lookup_record(session, name, record_type))
    debug(f"{domain} 查询到的 {record_type} 记录：{contents}")
    total_num = sum(len(content) for content in contents)
    if total_num + extra_num > ServerCfg.max_content_num:
        warning(
            f"{domain} 的记录数 {total_num + extra_num} 超过了设置的最大记录数 {ServerCfg.max_content_num}"
        )
        if record_type in {"A", "AAAA"}:
            record_by_org = defaultdict(list)
            for content in contents:
                for record in content:
                    record_by_org[get_ip_org(record, session)].append(record)
            contents = sorted(record_by_org.values(), key=len, reverse=True)
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


def setup_credentials():
    """
    配置认证信息（ak和sk）
    """
    ServerCfg.headers = {"Content-Type": "application/json"}
    try:
        ServerCfg.credentials = (
            EnvCredentialProvider.get_basic_credential_env_provider().get_credentials()
        )
        info("检测到环境变量 HUAWEICLOUD_SDK_AK 和 HUAWEICLOUD_SDK_SK，将使用环境变量中的凭证")
    except ApiValueError:
        if ServerCfg.hw_api_ak and ServerCfg.hw_api_sk:
            ServerCfg.credentials = BasicCredentials(
                ServerCfg.hw_api_ak, ServerCfg.hw_api_sk
            )
            info("检测到配置文件中的凭证，将使用配置文件中的凭证")
        else:
            critical("错误：未找到 API 凭证")
            sys.exit(1)


def get_zones(hwdns_client: DnsClient) -> list:
    """
    查询DNS Zone列表（包含域名）
    """
    info("正在查询 Zone 列表……")
    try:
        response: ListPublicZonesResponse = hwdns_client.list_public_zones(
            ListPublicZonesRequest()
        )
        zones: list[PublicZoneResp] = response.zones
        while response.links.next:
            response: ListPublicZonesResponse = hwdns_client.list_public_zones(
                ListPublicZonesRequest(offset=len(zones))
            )
            zones.extend(response.zones)
    except ClientRequestException as e:
        critical("错误：查询 Zone 列表失败：")
        critical(f"状态码：{e.status_code}")
        critical(f"请求ID：{e.request_id}")
        critical(f"错误码：{e.error_code}")
        critical(f"错误信息：{e.error_msg}")
        sys.exit(1)
    zone_msg = "，".join(f"{zone.name}：{zone.id}" for zone in zones)
    debug(f"查询到 {len(zones)} 个 Zone：{zone_msg}")
    return zones


def get_recordset_list(
    hwdns_client: DnsClient, zones: list[PublicZoneResp], up_item: UpItem
) -> tuple[str, dict] | None:
    # 切割域名，获取主域名和对应 Zone ID
    for zone in zones:
        if up_item.name.endswith(zone.name):
            zone_name = zone.name
            zone_id = zone.id
            info(f"{up_item.name} 对应的主域名：{zone_name}，对应的 Zone ID：{zone_id}")
            break
    else:
        ServerCfg.error_occurred = True
        error(f"错误：未找到 {up_item.name} 对应的主域名，请检查配置文件中的 domain 的主域名是否已添加到华为云 DNS 的公网域名")
        return None

    # 获取 Zone 下的 Record Set 列表
    info(f"正在查询 {zone_name} 下的记录列表……")
    try:
        response: ListRecordSetsByZoneResponse = hwdns_client.list_record_sets_by_zone(
            ListRecordSetsByZoneRequest(zone_id)
        )
        recordsets: list[ListRecordSets] = response.recordsets
        while response.links.next:
            response = hwdns_client.list_record_sets_by_zone(
                ListRecordSetsByZoneRequest(zone_id, offset=len(recordsets))
            )
            recordsets.append(response.recordsets)

    except ClientRequestException as e:
        critical("错误：查询 Zone 下的 Record Set 列表失败：")
        critical(f"状态码：{e.status_code}")
        critical(f"请求ID：{e.request_id}")
        critical(f"错误码：{e.error_code}")
        critical(f"错误信息：{e.error_msg}")
        sys.exit(1)

    recordset_list = []
    for recordset in recordsets:
        if recordset.name == up_item.name and recordset.type == up_item.record_type:
            recordset_list.append(recordset)
    return zone_id, recordset_list


def update_recordset(
    hwdns_client: DnsClient, zone_id: str, recordset: ListRecordSets, up_item: UpItem
) -> bool:
    info(f"正在更新 {up_item.name} 的 {up_item.record_type} 记录……")
    try:
        hwdns_client.update_record_set(
            UpdateRecordSetRequest(
                zone_id,
                recordset.id,
                UpdateRecordSetReq(
                    name=up_item.name,
                    description=up_item.description,
                    type=up_item.record_type,
                    records=up_item.content,
                    ttl=up_item.ttl,
                ),
            )
        )
        return True
    except ClientRequestException as e:
        error("错误：更新 Record Set 失败：")
        error(f"状态码：{e.status_code}")
        error(f"请求ID：{e.request_id}")
        error(f"错误码：{e.error_code}")
        error(f"错误信息：{e.error_msg}")
        return False


def add_recordset(hwdns_client: DnsClient, zone_id: str, up_item: UpItem) -> bool:
    try:
        hwdns_client.create_record_set_with_line(
            CreateRecordSetRequest(
                zone_id,
                CreateRecordSetRequestBody(
                    name=up_item.name,
                    description=up_item.description,
                    type=up_item.record_type,
                    ttl=up_item.ttl,
                    records=up_item.content,
                ),
            )
        )
        return True
    except ClientRequestException as e:
        error("错误：新增 Record Set 失败：")
        error(f"状态码：{e.status_code}")
        error(f"请求ID：{e.request_id}")
        error(f"错误码：{e.error_code}")
        error(f"错误信息：{e.error_msg}")
        return False


def set_recordset_status(
    hwdns_client: DnsClient, recordset_id: str, status: str = "DISABLE"
) -> bool:
    try:
        if status not in {"DISABLE", "ENABLE"}:
            ServerCfg.error_occurred = True
            error(f"错误：无效记录集的状态：{status}")
            return False
        hwdns_client.set_record_sets_status(
            SetRecordSetsStatusRequest(recordset_id, SetRecordSetsStatusReq(status))
        )
        return True
    except ClientRequestException as e:
        error("错误：设置 Record Set 状态失败：")
        error(f"状态码：{e.status_code}")
        error(f"请求ID：{e.request_id}")
        error(f"错误码：{e.error_code}")
        error(f"错误信息：{e.error_msg}")
        return False


async def run():
    if sys.gettrace():
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(
        format="[%(asctime)s][%(process)d][%(funcName)s (%(filename)s:%(lineno)d)]: [%(levelname)s]: %(message)s",
        level=log_level,
    )
    info("欢迎使用 dns-record-manager，基于 GPL-3.0 协议开源")
    up_item_list: list[UpItem] = await read_config()
    setup_credentials()
    session: aiohttp.ClientSession = aiohttp.ClientSession()
    regions: list = await select_region(session)
    for region in regions:
        region = dns_region.DnsRegion.static_fields[region]
        # 创建服务客户端
        try:
            if log_level is logging.DEBUG:
                hwdns_client = (
                    DnsClient.new_builder()
                    .with_credentials(ServerCfg.credentials)
                    .with_region(region)
                    .with_stream_log(log_level)
                    .with_http_handler(HttpHandler().add_response_handler(response_handler))
                    .build()
                )
            else:
                hwdns_client = (
                    DnsClient.new_builder()
                    .with_credentials(ServerCfg.credentials)
                    .with_region(region)
                    # .with_stream_log(log_level)
                    .build()
                )
            break
        except ApiValueError:
            continue
    zones = get_zones(hwdns_client)
    for up_item in up_item_list:
        # 查询 源记录 中的 值
        if up_item.sources:
            info(f"正在查询 {up_item.name} 设置的 {up_item.record_type} 记录……")
            up_item.content.extend(
                await lookup_records(
                    up_item.sources,
                    up_item.record_type,
                    session,
                    up_item.name,
                    len(up_item.content),
                )
            )
        recordset_list = get_recordset_list(hwdns_client, zones, up_item)
        if recordset_list is None:
            continue
        else:
            zone_id, recordsets = recordset_list
        if not recordsets:
            if up_item.content:
                info(f"正在添加 {up_item.name} 设置的 {up_item.record_type} 记录……")
                add_recordset(hwdns_client, zone_id, up_item)
                continue
            else:
                warning(f"{up_item.name} 没有 {up_item.record_type} 记录需要更新、禁用或添加")
                continue
        for recordset in recordsets:
            debug(f"正在处理 {up_item.name} 的 {recordset.id} 记录集……")
            query_recordset_result: ListRecordSets = hwdns_client.show_record_set(
                ShowRecordSetRequest(zone_id, recordset.id)
            )
            if query_recordset_result.description is None:
                query_recordset_result.description = ""
            if query_recordset_result.description == up_item.description and set(
                query_recordset_result.records
            ) == set(up_item.content):
                info(f"{up_item.name} 的 {query_recordset_result.id} 记录集没有变化，将跳过")
                continue
            if query_recordset_result.status != "ACTIVE":
                info(
                    f"{up_item.name} 的 {query_recordset_result.id} 记录集状态为 {query_recordset_result.status}，将跳过"
                )
                continue
            if up_item.match_description and not re.search(
                up_item.match_description, (query_recordset_result.description)
            ):
                info(f"{up_item.name} 的 {query_recordset_result.id} 记录集描述不匹配，将跳过")
                continue
            if up_item.content:
                # 更新记录集
                update_recordset(hwdns_client, zone_id, recordset, up_item)
            else:
                info(f"{up_item.name} 要设置的 {up_item.record_type} 记录集为空，将禁用现有记录集……")
                set_recordset_status(hwdns_client, recordset.id, "DISABLE")
    if session:
        await session.close()
        info("已关闭会话")
    if ServerCfg.error_occurred:
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(run())
