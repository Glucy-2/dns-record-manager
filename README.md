#  dns-record-merger
用于获取多个DNS的记录值合并，使用GitHub Action定时或本地运行通过华为云DNS的API更新 
## 协议
本项目使用 GPL v3 协议
## 使用方法
两种使用方法选择一种即可
### 使用 GitHub Action 定时执行
    1. Fork 本项目
    2. 开启项目的 Actions 功能
    3. 在项目 Settings -> Secrets and variables -> Actions 中添加环境变量
        - 在[这里](//console.huaweicloud.com/iam/#/mine/apiCredential)新增并下载华为云凭证访问密钥
        - `HW_API_KEY`内容为访问密钥的Access Key Id
        - `HW_API_SECRET`内容为访问密钥的Secret Access Key
    4. [修改配置文件](#配置文件)
    5. 默认每个半点执行一次、代码变动执行一次，如有需要可自行修改项目中的 `.github/workflows/update-dns.yml`
### 本地运行
    1. 安装 Python 3.6+ 环境（已在 Python 3.6.8 和 3.11.2 中测试通过）
    2. 下载本项目
    3. 安装依赖（`dnspython` `Requests` `requests-toolbelt`）
    4. [修改配置文件](#配置文件)
    5. 设置定时任务或手动执行
## 注意事项
- 使用本项目可能会导致服务商认为你没有将域名解析到其官方CNAME上
- 使用本项目可能会导致CDN上基于文件验证的SSL（TLS）证书无法获取
## 配置文件
- 配置文件存储在config.json中，使用时请不要在其中写注释
```json5
{
    "server_config": {
        // DNS over HTTPS 查询服务器，可以参考 https://dns.icoa.cn/dot-doh/ 中各项的DoH地址
        "dns_query_server": "https://cloudflare-dns.com/dns-query",
        // 华为云API各项设置
        // 此设置中的 ak 和 sk 的使用优先级比环境变量中的低，如果已配置环境变量则可以不修改
        "hw_api": {
            "scheme": "https", // 协议
            "endpoint": "dns.myhuaweicloud.com", // API终端节点，参考 https://developer.huaweicloud.com/endpoint?DNS
            "ak": "QTWAOY********VKYUC", // 访问密钥的Access Key Id
            "sk": "MFyfvK41ba2giqM7**********KGpownRZlmVmHc" //访问密钥的Secret Access Key
        }
    },
    // 需要更新的项目列表
    "update_items": [
        {
            "hostname": "skimit.net", // 域名
            "enable_ipv4": true, // 是否启用IPv4解析
            "enable_ipv6": true, // 是否启用IPv6解析
            "cname_records": [ // 要添加的 IP 来源 CNAME 列表
                "13651f0bb6f16c90.qaxwzws.com",
                "skimit.net.s2-web.dogedns.com",
                "skimit-homepage.b0.aicdn.com"
            ],
            "ipv4_ips": ["1.1.1.1"], // 额外添加的 IPv4 列表（可选）
            "ipv6_ips": [], // 额外添加的 IPv6 列表（可选）
            "description": "", // 添加到 DNS 记录集中的描述
            "ttl": 300 // DNS 记录的 TTL
        },
        {
            "hostname": "www.skimit.net",
            "enable_ipv4": true,
            "enable_ipv6": true,
            "cname_records": [
                "skimit.net.s2-web.dogedns.com",
                "skimit-homepage.b0.aicdn.com",
                "abcdefg13456789.cloudfront.net"
            ],
            "ipv4_ips": [],
            "ipv6_ips": [
                "240c::6666",
                "240c::6644"
            ],
            "description": "",
            "ttl": 300
        }
    ]
}
```