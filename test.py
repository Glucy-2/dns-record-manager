import time
import requests
from dns_record_manager import query_record
with requests.sessions.Session() as session:
    try:
        #tw_ip = query_record("tw-tpe-2023-07-01-00.skimit.net", "A", session)[0]
        #us_ip = query_record("us-ca-2022-11-18-00.skimit.net", "A", session)[0]
        #us2_ip = query_record("us-ca-2023-06-30-00.skimit.net", "A", session)[0]
        #hk_ip = query_record("cn-hk-2021-08-03-00.skimit.net", "A", session)[0]
        #hk2_ip = query_record("cn-hk-2023-06-07-00.skimit.net", "A", session)[0]
        #jp_ip = query_record("jp-13-2023-06-22-00.skimit.net", "A", session)[0]
        #zj_ip = query_record("cn-zj-2022-11-12-00.skimit.net", "A", session)[0]
        #dg_plan_ip = query_record("plan.skimit.net.s2-web.dogedns.com", "A", session)[0]
        #dg_bluemap_ip = query_record("bluemap.skimit.net.s2-web.dogedns.com", "A", session)[0]
        #up_plan_ip = query_record("skimit-plan.b0.aicdn.com", "A", session)[0]
        #up_bluemap_ip = query_record("skimit-bluemap.b0.aicdn.com", "A", session)[0]
        #gc_ip = "81.28.12.12"
        #cf_ip = query_record("cf-saas.skimit.top", "A", session)[0]
        cachefly_ip = query_record("skimithomepage.cachefly.net", "A", session)[0]
        #print(f"现在是 {time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))}")
        #print(f"tw-tpe-2023-07-01-00 上的 Plan    : {requests.get(f'http://{tw_ip}:8080/',headers={'Host':'plan.skimit.net'},verify=False).status_code}")
        #print(f"tw-tpe-2023-07-01-00 上的 Bluemap : {requests.get(f'http://{tw_ip}:8080/',headers={'Host':'bluemap.skimit.net'},verify=False).status_code}")
        #print(f"us-ca-2023-06-30-00  上的 Plan    : {requests.get(f'http://{us2_ip}:8080/',headers={'Host':'plan.skimit.net'},verify=False).status_code}")
        #print(f"us-ca-2023-06-30-00  上的 Bluemap : {requests.get(f'http://{us2_ip}:8080/',headers={'Host':'bluemap.skimit.net'},verify=False).status_code}")
        #print(f"us-ca-2022-11-18-00  上的 Plan    : {requests.get(f'http://{us_ip}:8080/',headers={'Host':'plan.skimit.net'},verify=False).status_code}")
        #print(f"us-ca-2022-11-18-00  上的 Bluemap : {requests.get(f'http://{us_ip}:8080/',headers={'Host':'bluemap.skimit.net'},verify=False).status_code}")
        #print(f"jp-13-2023-06-22-00  上的 Plan    : {requests.get(f'http://{jp_ip}:8080/',headers={'Host':'plan.skimit.net'},verify=False).status_code}")
        #print(f"jp-13-2023-06-22-00  上的 Bluemap : {requests.get(f'http://{jp_ip}:8080/',headers={'Host':'bluemap.skimit.net'},verify=False).status_code}")
        #print(f"cn-hk-2023-06-07-00  上的 Plan    : {requests.get(f'http://{hk2_ip}:8080/',headers={'Host':'plan.skimit.net'},verify=False).status_code}")
        #print(f"cn-hk-2023-06-07-00  上的 Bluemap : {requests.get(f'http://{hk2_ip}:8080/',headers={'Host':'bluemap.skimit.net'},verify=False).status_code}")
        #print(f"cn-hk-2021-08-03-00  上的 Plan    : {requests.get(f'http://{hk_ip}:8080/',headers={'Host':'plan.skimit.net'},verify=False).status_code}")
        #print(f"cn-hk-2021-08-03-00  上的 Bluemap : {requests.get(f'http://{hk_ip}:8080/',headers={'Host':'bluemap.skimit.net'},verify=False).status_code}")
        #print(f"cn-zj-2022-11-12-00  上的 Plan    : {requests.get(f'http://{zj_ip}:31000/',headers={'Host':'plan.skimit.net'},verify=False).status_code}")
        #print(f"cn-zj-2022-11-12-00  上的 Bluemap : {requests.get(f'http://{zj_ip}:31000/',headers={'Host':'bluemap.skimit.net'},verify=False).status_code}")
        #print(f"        多吉云        上的 Plan    : {requests.get(f'https://{dg_plan_ip}/',headers={'Host':'plan.skimit.net'},verify=False).status_code}")
        #print(f"        多吉云        上的 Bluemap : {requests.get(f'https://{dg_bluemap_ip}/',headers={'Host':'bluemap.skimit.net'},verify=False).status_code}")
        #print(f"        又拍云        上的 Plan    : {requests.get(f'https://{up_plan_ip}/',headers={'Host':'plan.skimit.net'},verify=False).status_code}")
        #print(f"        又拍云        上的 Bluemap : {requests.get(f'https://{up_bluemap_ip}/',headers={'Host':'bluemap.skimit.net'},verify=False).status_code}")
        #print(f"        GCore        上的 Plan    : {requests.get(f'https://{gc_ip}/',headers={'Host':'plan.skimit.net'},verify=False).status_code}")
        #print(f"        GCore        上的 Bluemap : {requests.get(f'https://{gc_ip}/',headers={'Host':'bluemap.skimit.net'},verify=False).status_code}")
        #print(f"      CloudFlare     上的 Plan    : {requests.get(f'http://{cf_ip}:8080/',headers={'Host':'bluemap.skimit.net'},verify=False).status_code}")
        #print(f"      CloudFlare     上的 Bluemap : {requests.get(f'http://{cf_ip}:8080/',headers={'Host':'bluemap.skimit.net'},verify=False).status_code}")
        print(f"       CacheFly      上的 Homepage: {requests.get(f'https://{cachefly_ip}/',headers={'Host':'skimit.net'},verify=False).status_code}")
        # time.sleep(10)
        # continue
        exit()
    except:
        pass
