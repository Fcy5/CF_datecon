import http.client
import json

from CF_updatecon.app import get_campaign_id_by_name

API_KEY = "0cd87c1ce7251b3aa8414f3613b259b3e282bf7c66cd56f4ae2913eeb53c5ee0.e2deb7cb288cc2544c1836a235f25ab3f59bcfb6"


# def test_api_directly():
#     """ http.client 测试 API"""
#     conn = http.client.HTTPSConnection("public-api.clickflare.io")
#     headers = {
#         "api-key": API_KEY,
#         "Content-Type": "application/json",
#         "Accept": "application/json"
#     }
#
#     payload = {
#         "startDate": "2025-07-10 00:00:00",
#         "endDate": "2025-07-11 00:00:00",
#         "metrics": ["ClickID",
#                     "EventType",
#                     "CampaignID",
#                     "VisitTime",
#                     "ClickTime"],
#         "timezone": "Asia/Shanghai",
#         "sortBy": "ClickID",
#         "orderType": "asc",
#         "page": 1,
#         "pageSize": 10,
#     "metricsFilters": [
#         {
#             "name": "CampaignID",
#             "operator": "in",
#             "value": [
#                 "68688b85c1a4a20012a6a315"
#             ]
#         }
#     ],
#         "includeFilteredEvents": True
#     }
#
#     conn.request("POST", "/api/event-logs", json.dumps(payload), headers)
#     response = conn.getresponse()
#
#     print("状态码:", response.status)
#     print("响应头:", response.getheaders())
#     print("响应体:", response.read().decode())
#
#     conn.close()
#
#
# test_api_directly()


def get_campaign_traffic_source(campaign_id):
    """根据活动ID获取活动详情，返回接口所有返回值及提取的流量源信息"""
    conn = http.client.HTTPSConnection("public-api.clickflare.io")
    headers = {"api-key": API_KEY}
    result = {}  # 用于存储所有返回信息

    try:
        # 构造请求路径
        request_path = f"/api/campaigns/{campaign_id}"
        conn.request("GET", request_path, headers=headers)
        response = conn.getresponse()

        # 检查响应状态
        if response.status != 200:
            raise Exception(f"获取活动详情失败: 状态码 {response.status}，响应: {response.read().decode()}")

        # 解析完整响应数据
        campaign_details = json.loads(response.read().decode())
        print(f"活动详情完整响应: {campaign_details}")

        # 提取流量源相关信息（核心字段）
        traffic_source_info = {
            "traffic_source_id": campaign_details.get("traffic_source_id"),
            "campaign_id": campaign_details.get("_id"),
            "campaign_name": campaign_details.get("name"),
            "tracking_type": campaign_details.get("tracking_type"),
            "cost_type": campaign_details.get("cost_type")
        }

        # 组装结果：包含所有返回字段 + 提取的核心信息
        result = {
            "full_details": campaign_details,  # 接口返回的所有原始字段
            "traffic_source_info": traffic_source_info,  # 提取的流量源相关信息
            "status": "success"
        }

        if not traffic_source_info["traffic_source_id"]:
            print(f"活动 {campaign_id} 未关联流量源")
            result["warning"] = "活动未关联流量源"

    except Exception as e:
        error_msg = f"获取流量源信息失败: {str(e)}"
        print(error_msg)
        result = {
            "status": "error",
            "message": error_msg
        }
        raise  # 向上抛出异常，便于调用方处理
    finally:
        conn.close()

    return result

def main(campaign_name):
    try:
        # 1. 根据活动名称获取活动ID
        campaign_id = get_campaign_id_by_name(campaign_name)

        # 2. 根据活动ID获取流量源信息
        traffic_source = get_campaign_traffic_source(campaign_id)

        print(f"活动 {campaign_name} 的流量源信息: {traffic_source}")
        return traffic_source

    except Exception as e:
        print(f"流程执行失败: {str(e)}")
        return None



target_campaign = "Mintegral_FCY_8221_DollarTree500_20250709_ios"  # 活动名称
result = main(target_campaign)
print(result)