#  dns-record-manager
用于获取多个DNS的记录值合并，使用GitHub Action定时或本地运行通过华为云DNS的API更新  
![GitHub Workflow Status](https://github.com/Glucy-2/dns-record-manager/actions/workflows/update-dns.yml/badge.svg)
## 协议
本项目使用 GPL v3 协议
## 使用方法
两种使用方法选择一种即可
### 使用 GitHub Action 定时执行
    1. Fork 本项目
    2. 开启项目的 Actions 功能
    3. 在项目 Settings -> Secrets and variables -> Actions 中添加环境变量
        - 在[这里](//console.huaweicloud.com/iam/#/mine/apiCredential)新增并下载华为云凭证访问密钥
        - `HW_API_KEY`内容为访问密钥的 Access Key Id
        - `HW_API_SECRET`内容为访问密钥的 Secret Access Key
    4. [修改配置文件](#配置文件)
    5. 默认每个半点执行一次、代码变动执行一次，如有需要可自行修改项目中的 `.github/workflows/update-dns.yml`
### 本地运行
    1. 安装 Python 3.10+ 环境（已在 Python 3.11.2 中测试通过）
    2. 下载本项目
    3. 安装依赖（`dnspython` `Requests` `requests-toolbelt`）
    4. [修改配置文件](#配置文件)
    5. 设置定时任务或手动执行
## 注意事项
- 使用本项目可能会导致服务商认为你没有将域名解析到其官方CNAME上
- 使用本项目可能会导致CDN上基于文件验证的SSL（TLS）证书无法获取，你可以尝试设置CAA记录
## 配置文件
- 配置文件存储在config.json中，使用时请不要在其中写注释
```json
{
    "server_config": {
        // DNS over HTTPS 查询服务器，可以参考 https://dns.icoa.cn/dot-doh/ 中各项的DoH地址
        "dns_query_server": "https://cloudflare-dns.com/dns-query",
        // User-Agent
        "ua": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/113.0",
        // 华为云API各项设置
        // 此设置中的 ak 和 sk 的使用优先级比环境变量中的低，如果已配置环境变量则可以不修改
        "hw_api": {
            "scheme": "https", // 协议
            "endpoint": "dns.myhuaweicloud.com", // API终端节点，参考 https://developer.huaweicloud.com/endpoint?DNS
            "ak": "QTWAOY********VKYUC", // 访问密钥的Access Key Id
            "sk": "MFyfvK41ba2giqM7**********KGpownRZlmVmHc" //访问密钥的Secret Access Key
        },
        // 解析记录最大条数，华为云最大50
        "max_content_num": 50
    },
    // 需要更新的项目列表
    "update_items": [
        {
            "enabled": true, // （可选）是否启用
            "domain": "skimit.net", // （必填）域名，可以是字符串或字符串列表
            "type": "A", // （必填）记录类型，可以是字符串或字符串列表，支持 A，AAAA，MX，TXT，SRV，NS，CAA
            "sources": [ // （必填）记录值来源，字符串列表
                "13651f0bb6f16c90.qaxwzws.com",
                "skimit.net.s2-web.dogedns.com",
                "skimit-homepage.b0.aicdn.com"
            ],
            "extra": [], // （可选）额外的记录值，字符串列表
            "match_description": "", // （可选）用户匹配记录集描述的正则表达式，如果为非空值则只有匹配的记录集才会被更新，如果填写并不想只处理一次请保证descript的值能匹配
            "description": "奇安信，多吉云，又拍云", // （可选）记录集描述，不填则为sources的合并
            "ttl": 300 // （可选）TTL，不填则为300
        },
        {
            "enabled": true,
            "domain": [
                "skimit.net",
                "www.skimit.net"
            ],
            "type": "AAAA",
            "sources": [
                "skimit.net.s2-web.dogedns.com",
                "skimit-homepage.b0.aicdn.com"
            ],
            "extra": [],
            "match_description": "",
            "description": "多吉云，又拍云",
            "ttl": 300
        },
        {
            "enabled": true,
            "domain": "www.skimit.net",
            "type": "A",
            "sources": [
                "skimit.net.s2-web.dogedns.com",
                "skimit-homepage.b0.aicdn.com"
            ],
            "extra": [],
            "match_description": "",
            "description": "多吉云，又拍云",
            "ttl": 300
        }
    ]
}
```
## TODO（画饼）
- 直接使用huaweicloudsdkdns包
- 异步
- 解析线路设置与匹配
- Tag 设置与匹配