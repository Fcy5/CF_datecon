import http.client
import json

API_KEY = "0cd87c1ce7251b3aa8414f3613b259b3e282bf7c66cd56f4ae2913eeb53c5ee0.e2deb7cb288cc2544c1836a235f25ab3f59bcfb6"


def get_campaign_id_by_name(campaign_name):
    """根据名称获取活动ID"""
    conn = http.client.HTTPSConnection("public-api.clickflare.io")
    headers = {"api-key": API_KEY}

    try:
        # 使用名称作为查询参数
        query = f"/api/campaigns/list?query={campaign_name}"
        conn.request("GET", query, headers=headers)
        response = conn.getresponse()

        if response.status != 200:
            raise Exception(f"API调用失败: 状态码 {response.status}")

        data = json.loads(response.read().decode())

        # 查找匹配的campaign
        for campaign in data:
            if campaign.get("name", "").lower() == campaign_name.lower():
                print(f"找到匹配活动: {campaign_name} → ID: {campaign['_id']}")
                return campaign["_id"]

        # 没有找到匹配项
        available_names = ", ".join([c.get("name", "") for c in data])
        raise ValueError(f"未找到名为 '{campaign_name}' 的活动。可用活动: {available_names}")

    finally:
        conn.close()


def query_event_logs(campaign_ids):
    """使用活动ID查询事件日志"""
    conn = http.client.HTTPSConnection("public-api.clickflare.io")
    headers = {
        "api-key": API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


    essential_metrics = [
        "ClickID", "CampaignID", "EventType", "ClickTime"
    ]

    payload = {
        "startDate": "2025-07-11 00:00:00",
        "endDate": "2025-07-11 23:59:59",
        "metrics": essential_metrics,
        "timezone": "Asia/Shanghai",
        "sortBy": "ClickTime",
        "orderType": "desc",
        "page": 1,
        "pageSize": 100,
        "metricsFilters": [
            {
                "name": "CampaignID",
                "operator": "in",
                "value": campaign_ids
            }
        ],
        "includeFilteredEvents": True
    }

    try:
        print(f"正在查询活动ID: {campaign_ids}")
        conn.request("POST", "/api/event-logs", json.dumps(payload), headers)
        response = conn.getresponse()

        print(f"响应状态: {response.status}")
        data = response.read().decode()

        if response.status != 200:
            print(f"响应头: {response.getheaders()}")
            print(f"响应体: {data}")
            raise Exception(f"事件日志查询失败: {response.status}")

        return json.loads(data)

    finally:
        conn.close()


def main():
    # 第一步：获取活动ID
    campaign_name = "Mintegral_FCY_8221_cashapp500_20250705_2"  # 替换为您要查询的活动名称
    try:
        campaign_id = get_campaign_id_by_name(campaign_name)
        campaign_ids = [str(campaign_id)]  # 确保是列表形式

        # 第二步：查询事件日志
        logs_data = query_event_logs(campaign_ids)

        # 处理结果
        print("\n查询结果摘要:")
        print(f"总记录数: {logs_data.get('total', 0)}")
        print(f"返回记录数: {len(logs_data.get('data', []))}")

        # 保存结果到文件
        with open(f'event_logs_{campaign_name}.json', 'w') as f:
            json.dump(logs_data, f, indent=2)
            print(f"结果已保存到 event_logs_{campaign_name}.json")

        # 打印前几条记录（可选）
        if logs_data.get('data'):
            print("\n前5条记录示例:")
            for i, record in enumerate(logs_data['data'][:5]):
                print(f"[{i + 1}] ID:{record.get('ClickID')} | "
                      f"时间:{record.get('ClickTime')} | "
                      f"事件:{record.get('EventType')} | "
                      f"国家:{record.get('LocationCountryName')}")

    except Exception as e:
        print(f"错误: {str(e)}")


if __name__ == "__main__":
    main()