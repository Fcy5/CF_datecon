import hashlib
import re
import threading

import requests
import webview
import sys
import os
from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import http.client
import json
import socket
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

if getattr(sys, 'frozen', False):
    # 打包后的环境
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    app = Flask(__name__, template_folder=template_folder)
else:
    # 开发环境
    app = Flask(__name__)

# ClickFlare操作接口
# ClickFlare API 配置
API_KEY = "0cd87c1ce7251b3aa8414f3613b259b3e282bf7c66cd56f4ae2913eeb53c5ee0.e2deb7cb288cc2544c1836a235f25ab3f59bcfb6"
CONVERSION_UPLOAD_API_URL = "https://public-api.clickflare.io/api/raw-conversion-uploader/upload"
CLICKFLARE_API_HOST = "public-api.clickflare.io"


def get_campaign_id_by_name(campaign_name):
    """根据名称获取活动ID"""
    conn = http.client.HTTPSConnection("public-api.clickflare.io")
    headers = {"api-key": API_KEY}
    campaign_id = None

    try:
        # 使用名称作为查询参数
        query = f"/api/campaigns/list?query={campaign_name}"
        conn.request("GET", query, headers=headers)
        response = conn.getresponse()

        if response.status != 200:
            raise Exception(f"API调用失败: 状态码 {response.status}")

        data = json.loads(response.read().decode())
        print(data)
        logger.info(f"获取活动列表响应: {data}")

        # 查找匹配的campaign
        for campaign in data:
            if campaign.get("name", "").lower() == campaign_name.lower():
                campaign_id = campaign["_id"]
                logger.info(f"找到匹配活动: {campaign_name} → ID: {campaign_id}")
                break

        if not campaign_id:
            # 没有找到匹配项
            available_names = ", ".join([c.get("name", "") for c in data])
            raise ValueError(f"未找到名为 '{campaign_name}' 的活动。可用活动: {available_names}")

    except Exception as e:
        logger.error(f"获取活动ID失败: {str(e)}")
        raise
    finally:
        conn.close()

    return campaign_id


@app.route('/api/get_tracking_report', methods=['POST'])
def get_tracking_report():
    """根据活动ID查询trackingField7报告数据（修复筛选条件格式）"""
    try:
        data = request.json

        # 验证必要参数
        required_fields = ['campaign_id', 'start_date', 'end_date', 'timezone']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "success": False,
                    "error": f"缺少必要参数: {field}"
                }), 400

        # 解析参数
        campaign_id = data['campaign_id']
        start_date = data['start_date']
        end_date = data['end_date']
        timezone = data['timezone']
        sort_by = data.get('sort_by', 'trackingField7')
        order_type = data.get('order_type', 'asc')
        page = data.get('page', 1)
        page_size = data.get('page_size', 30)

        # 解析筛选参数
        min_visits = data.get('min_visits')  # 最小访问量
        min_conversions = data.get('min_conversions')  # 最小转化数

        # 转换时区
        timezone_mapping = {
            "+8": "Asia/Shanghai",
            "-4": "America/New_York",
            "-8": "America/Los_Angeles"
        }
        iana_timezone = timezone_mapping.get(timezone, "UTC")

        # 构造基础筛选条件（活动ID）
        metrics_filters = [
            {
                "name": "campaignID",
                "operator": "in",
                "value": [campaign_id]  # 注意：campaignID是字符串类型，需要用数组
            }
        ]

        # 修复：访问量筛选（value改为单个数字，而非数组）
        if min_visits is not None and str(min_visits).isdigit():
            metrics_filters.append({
                "name": "visits",
                "operator": ">=",
                "value": int(min_visits)  # 关键修复：去掉数组括号[]
            })

        # 修复：转化数筛选（value改为单个数字，而非数组）
        if min_conversions is not None and str(min_conversions).isdigit():
            metrics_filters.append({
                "name": "conversions",
                "operator": "<=",
                "value": int(min_conversions)  # 关键修复：去掉数组括号[]
            })

        # 构造请求体
        payload = {
            "startDate": start_date,
            "endDate": end_date,
            "groupBy": ["trackingField7"],
            "metrics": [
                "trackingField7", "visits", "uniqueVisits", "clicks",
                "revenue", "conversions", "ctr", "cvr", "epc", "roi"
            ],
            "timezone": iana_timezone,
            "sortBy": sort_by,
            "orderType": order_type,
            "page": page,
            "pageSize": page_size,
            "includeAll": False,
            "conversionTimestamp": "visit",
            "metricsFilters": metrics_filters  # 应用修复后的筛选条件
        }

        # 发送请求
        conn = http.client.HTTPSConnection(CLICKFLARE_API_HOST)
        headers = {
            "api-key": API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        conn.request("POST", "/api/report", json.dumps(payload), headers)
        response = conn.getresponse()
        response_data = response.read().decode()

        # 处理响应
        if response.status != 200:
            logger.error(f"报告API请求失败: 状态码 {response.status}, 响应: {response_data}")
            return jsonify({
                "success": False,
                "error": f"报告查询失败，状态码: {response.status}",
                "details": response_data
            }), response.status

        result = json.loads(response_data)
        return jsonify({
            "success": True,
            "data": {
                "tracking_data": result.get("items", []),
                "totals": result.get("totals", {}),
                "page_info": {
                    "current_page": page,
                    "page_size": page_size,
                    "total_items": result.get("totals", {}).get("counter", 0),
                    "total_pages": int(result.get("totals", {}).get("counter", 0) / page_size) + 1
                }
            }
        })

    except Exception as e:
        logger.exception("查询trackingField7报告异常")
        return jsonify({
            "success": False,
            "error": f"服务器错误: {str(e)}"
        }), 500


def query_event_logs(campaign_ids, start_date, end_date, timezone_offset, page=1, page_size=10):
    """使用活动ID查询事件日志（使用原始字段格式）"""
    conn = http.client.HTTPSConnection("public-api.clickflare.io")
    headers = {
        "api-key": API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    start_date_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
    end_date_str = end_date.strftime("%Y-%m-%d %H:%M:%S")

    timezone_mapping = {
        "+8": "Asia/Shanghai",
        "-4": "America/New_York",
        "-8": "America/Los_Angeles"
    }
    timezone_str = timezone_mapping.get(timezone_offset, "UTC")

    # 关键修复：使用您原始的大写字段名
    payload = {
        "startDate": start_date_str,
        "endDate": end_date_str,
        "metrics": ["ClickID", "EventType", "CampaignID", "VisitTime", "ClickTime"],
        "timezone": timezone_str,
        "sortBy": "ClickTime",
        "orderType": "desc",
        "page": page,
        "pageSize": page_size,
        "metricsFilters": [
            {
                "name": "CampaignID",
                "operator": "in",
                "value": [str(cid) for cid in campaign_ids]
            },
            {
                "name": "EventType",
                "operator": "=",
                "value": ["click"]  # 只获取点击事件
            }
        ],
        "includeFilteredEvents": True
    }

    try:
        conn.request("POST", "/api/event-logs", json.dumps(payload), headers)
        response = conn.getresponse()
        data = response.read().decode()

        if response.status != 200:
            return {"error": f"API错误: {response.status} - {data}"}

        json_data = json.loads(data)

        # 关键修复：使用原始大写字段格式
        click_events = []
        for item in json_data.get("items", []):
            if item.get("EventType") == "click":
                click_events.append({
                    "ClickID": item.get("ClickID", ""),
                    "EventType": item.get("EventType", ""),
                    "CampaignID": item.get("CampaignID", ""),
                    "VisitTime": item.get("VisitTime", ""),
                    "ClickTime": item.get("ClickTime", "")
                })

        return {
            "total": json_data.get("totals", {}).get("counter", 0),
            "page": page,
            "page_size": page_size,
            "results": click_events
        }
    finally:
        conn.close()


@app.route('/api/get_event_logs', methods=['POST'])
def api_get_event_logs():
    """API端点：获取事件日志数据"""
    data = request.get_json()
    logger.info(f"收到日志查询请求: {data}")

    # 验证输入
    required_fields = ["campaign_names", "start_date", "end_date", "timezone"]
    if not all(field in data for field in required_fields):
        error_msg = "缺少必要参数"
        logger.error(error_msg)
        return jsonify({"error": error_msg}), 400

    try:
        # 处理时间输入格式
        def parse_datetime(dt_str):
            # 支持您原有的格式
            formats = [
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M"
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(dt_str, fmt)
                except ValueError:
                    continue
            return datetime.now()  # 默认值

        # 原始时间处理逻辑
        start_date = parse_datetime(data["start_date"])
        end_date = parse_datetime(data["end_date"])

        # 获取活动ID
        campaign_ids = []
        for name in data["campaign_names"].split(","):
            campaign_id = get_campaign_id_by_name(name.strip())
            if campaign_id:
                campaign_ids.append(campaign_id)

        # 获取事件日志
        logs_data = query_event_logs(
            campaign_ids=campaign_ids,
            start_date=start_date,
            end_date=end_date,
            timezone_offset=data["timezone"],
            page=data.get("page", 1),
            page_size=data.get("page_size", 10)
        )

        # 保持您原有的返回结构
        return jsonify({
            "success": True,
            "total": logs_data["total"],
            "page": logs_data["page"],
            "page_size": logs_data["page_size"],
            "results": logs_data["results"]
        })

    except Exception as e:
        error_msg = f"查询失败: {str(e)}"
        logger.exception(error_msg)  # 记录完整堆栈
        return jsonify({"error": error_msg}), 500


def upload_to_clickflare(conversions):
    """批量上传转化数据到 ClickFlare"""
    conversion_lines = []

    for conv in conversions:
        click_id = conv.get("click_id", "")
        payout = conv.get("payout", 0)
        timestamp = datetime.utcnow().isoformat() + "Z"

        if not click_id or payout <= 0:
            continue

        line = f"{click_id},{payout},{timestamp}"
        conversion_lines.append(line)

    if not conversion_lines:
        return {"error": "没有有效的转化记录", "status_code": 400}

    conn = http.client.HTTPSConnection("public-api.clickflare.io")
    headers = {
        "api-key": API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "conversions": conversion_lines,
        "uploadOptions": {
            "shouldIgnorePostbacks": True
        }
    }

    try:
        logger.info(f"上传转化数据: {len(conversion_lines)}条记录")
        conn.request("POST", "/api/raw-conversion-uploader/upload", json.dumps(payload), headers)
        response = conn.getresponse()

        if response.status != 200:
            error = response.read().decode()
            logger.error(f"上传失败: {response.status} - {error}")
            return {"error": f"上传失败: {response.status} - {error}", "status_code": response.status}

        result = json.loads(response.read().decode())
        logger.info(f"上传成功: {result}")
        return result

    except Exception as e:
        logger.error(f"上传转化数据失败: {str(e)}")
        return {"error": f"上传失败: {str(e)}", "status_code": 500}
    finally:
        conn.close()


@app.route('/api/upload_conversions', methods=['POST'])
def api_upload_conversions():
    """处理转化数据上传"""
    try:
        data = request.get_json()
        logger.info(f"收到转化数据上传请求: {data}")

        if not data or 'conversions' not in data:
            error_msg = "无效的请求格式"
            logger.error(error_msg)
            return jsonify({"error": error_msg}), 400

        conversions = data['conversions']
        if not conversions:
            error_msg = "请提供转化数据"
            logger.error(error_msg)
            return jsonify({"error": error_msg}), 400

        # 上传到ClickFlare
        result = upload_to_clickflare(conversions)

        if "error" in result:
            status_code = result.get("status_code", 500)
            logger.error(f"上传失败: {result['error']}")
            return jsonify({
                "success": False,
                "error": result["error"]
            }), status_code

        # 返回成功响应
        uploaded_count = len(conversions)
        success_msg = f"成功上传 {uploaded_count} 条转化记录"
        logger.info(success_msg)
        return jsonify({
            "success": True,
            "message": success_msg,
            "response": result
        })

    except Exception as e:
        error_msg = f"服务器错误: {str(e)}"
        logger.error(error_msg)
        return jsonify({"error": error_msg}), 500


@app.route('/mtg.html')
def mtg_page():
    return render_template('mtg.html')


@app.route('/mtg_id.html')
def mtg_id_page():
    return render_template('mtg_id.html')


@app.route('/index.html')
def index_page():
    """显示主界面"""
    # 设置默认时间为最近7天
    default_end = datetime.now()
    default_start = default_end - timedelta(days=7)

    # 添加时区选项
    timezones = [
        {"value": "-8", "label": "UTC-8 (太平洋时间)"},
        {"value": "-4", "label": "UTC-4 (东部时间)"},
        {"value": "+8", "label": "UTC+8 (中国标准时间)"}
    ]

    # 格式化为前端datetime-local输入所需的格式：YYYY-MM-DDTHH:MM
    return render_template('index.html',
                           default_start=default_start.strftime("%Y-%m-%dT%H:%M"),
                           default_end=default_end.strftime("%Y-%m-%dT%H:%M"),
                           timezones=timezones,
                           default_timezone="+8")  # 默认选择中国时区


@app.route('/')
def index():
    """显示主界面"""
    # 设置默认时间为最近7天
    default_end = datetime.now()
    default_start = default_end - timedelta(days=7)

    # 添加时区选项
    timezones = [
        {"value": "-8", "label": "UTC-8 (太平洋时间)"},
        {"value": "-4", "label": "UTC-4 (东部时间)"},
        {"value": "+8", "label": "UTC+8 (中国标准时间)"}
    ]

    # 格式化为前端datetime-local输入所需的格式：YYYY-MM-DDTHH:MM
    return render_template('index.html',
                           default_start=default_start.strftime("%Y-%m-%dT%H:%M"),
                           default_end=default_end.strftime("%Y-%m-%dT%H:%M"),
                           timezones=timezones,
                           default_timezone="+8")  # 默认选择中国时区


# MTG操作接口
# Access Key和API Key
# HARDCODED_ACCESS_KEY = "157b51a428d2bcf8f837aed3690ca322"
# HARDCODED_API_KEY = "f5a790d556f481ff7ecc4a0e5ce8cad7"
HARDCODED_ACCESS_KEY = "5cc4db728653da2316ca9309d4ff894f"
HARDCODED_API_KEY = "8bf63783e0a77a56381ec81b2b935a8a"
MINTERGRAL_API_URL = "https://ss-api.mintegral.com/api/open/v1"
MINTERGRAL_CAMPAIGN_URL = "https://ss-api.mintegral.com/api/open/v1/campaign"
MINTERGRAL_UPLOAD_URL = "https://ss-storage-api.mintegral.com/api/open/v1/creatives/upload"
MINTERGRAL_PLAYABLE_URL = "https://ss-storage-api.mintegral.com/api/open/v1/playable/upload"
MINTERGRAL_CREATIVE_SETS_URL = "https://ss-api.mintegral.com/api/open/v1/creative_sets"  # 新增创意组查询地址
MINTERGRAL_CREATIVE_LIST_URL = "https://ss-api.mintegral.com/api/open/v1/creative-ad/list"
MINTERGRAL_CREATE_OFFER_URL = "https://ss-api.mintegral.com/api/open/v1/offer"

# 分类配置（按API要求）
IOS_CATEGORIES = "6018,6000,6022,6017,6016,6023,6014,6013,6012,6020,6011,6010,6009,6021,OTHERS,6008,6006,6024,6005,6004,6003,6002,6001"
# ANDROID_CATEGORIES = "GAME,ANDROID_WEAR,ART_AND_DESIGN,AUTO_AND_VEHICLES,BEAUTY,BOOKS_AND_REFERENCE,BUSINESS,COMICS,COMMUNICATION,DATING,EDUCATION,ENTERTAINMENT,EVENTS,FINANCE,FOOD_AND_DRINK,HEALTH_AND_FITNESS,HOUSE_AND_HOME,LIBRARIES_AND_DEMO,LIFESTYLE,MAPS_AND_NAVIGATION,MEDICAL,MUSIC_AND_AUDIO,NEWS_AND_MAGAZINES,OTHERS,PARENTING,PERSONALIZATION,PHOTOGRAPHY,PRODUCTIVITY,SHOPPING,SOCIAL,SPORTS,TOOLS,TRAVEL_AND_LOCAL,VIDEO_PLAYERS,WEATHER"

ANDROID_CATEGORIES = "TOOLS"


def generate_token(api_key, timestamp):
    timestamp_md5 = hashlib.md5(str(timestamp).encode('utf-8')).hexdigest()
    return hashlib.md5((api_key + timestamp_md5).encode('utf-8')).hexdigest()


def get_mintegral_headers():
    timestamp = int(time.time())
    headers = {
        "access-key": HARDCODED_ACCESS_KEY,
        "token": generate_token(HARDCODED_API_KEY, timestamp),
        "timestamp": str(timestamp),
        "Content-Type": "application/json"
    }
    logger.info(f"生成的请求头: {json.dumps(headers, ensure_ascii=False)}")
    return headers


def extract_keyword_from_campaign_name(campaign_name):
    pattern = r'([a-zA-Z]+\d+[a-zA-Z]?)'
    matches = re.findall(pattern, campaign_name)
    keyword = matches[-1] if matches else campaign_name[:100]
    logger.info(f"提取的关键词: {keyword}（原始名称: {campaign_name}）")
    return keyword


def upload_creative_file(file):
    try:
        file_content = file.read()
        headers = get_mintegral_headers()
        headers.pop("Content-Type", None)

        logger.info(f"上传的文件信息: 名称={file.filename}, 类型={file.content_type}")

        files = {'file': (file.filename, file_content, file.content_type)}
        upload_url = MINTERGRAL_UPLOAD_URL if not file.filename.lower().endswith(
            ('.zip', '.html')) else MINTERGRAL_PLAYABLE_URL
        logger.info(f"素材上传URL: {upload_url}")

        response = requests.post(upload_url, headers=headers, files=files, timeout=30)
        logger.info(f"素材上传响应: 状态码={response.status_code}, 内容={response.text}")

        try:
            result = response.json()
            if result.get('code') == 200:
                md5 = result['data'].get('creative_md5')
                logger.info(f"新上传素材MD5: {md5}")
                return {"success": True, "md5": md5, "is_existing": False}
            else:
                creative_name = result.get('data', {}).get('file.creative_name', '')
                if 'fmd5: ' in creative_name:
                    md5_start = creative_name.find('fmd5: ') + 5
                    md5_end = creative_name.find(',', md5_start)
                    md5 = creative_name[md5_start:md5_end].strip()
                    if len(md5) == 32:
                        logger.info(f"复用已存在素材MD5: {md5}")
                        return {"success": True, "md5": md5, "is_existing": True}
                logger.warning(f"素材上传失败，无法提取MD5: {result}")
                return {"success": False, "msg": f"上传失败: {result.get('msg')}"}
        except json.JSONDecodeError:
            logger.error(f"素材上传响应不是JSON格式: {response.text}")
            return {"success": False, "msg": "响应格式错误"}
    except Exception as e:
        logger.error(f"素材上传异常: {str(e)}", exc_info=True)
        return {"success": False, "msg": str(e)}


@app.route('/api/create_campaign_with_creative', methods=['POST'])
def create_campaign_with_creative():
    try:
        campaign_name = request.form.get('campaign_name')
        preview_url = request.form.get('preview_url')
        platform = request.form.get('platform')
        file = request.files.get('file')

        logger.info("\n===== 接收的请求参数 =====")
        logger.info(f"campaign_name: {campaign_name}")
        logger.info(f"preview_url: {preview_url}")
        logger.info(f"platform: {platform}")
        logger.info(f"file存在: {bool(file)}")
        logger.info("=========================\n")

        if not all([campaign_name, preview_url, platform, file]):
            err_msg = "缺少必要参数"
            logger.error(err_msg)
            return jsonify({"code": 400, "msg": err_msg}), 400

        keyword = extract_keyword_from_campaign_name(campaign_name)
        upload_result = upload_creative_file(file)
        if not upload_result['success'] or not upload_result.get('md5'):
            err_msg = f"素材处理失败: {upload_result['msg']}"
            logger.error(err_msg)
            return jsonify({"code": 400, "msg": err_msg}), 400
        creative_md5 = upload_result['md5']

        data = {
            "campaign_name": campaign_name[:100],
            "promotion_type": "WEBSITE",
            "preview_url": preview_url.strip(),
            "is_coppa": "NO",
            "alive_in_store": "NO",
            "product_name": keyword,
            "description": keyword,
            "icon": creative_md5,
            "platform": platform,
            "app_size": "",
            "min_version": "",
            "package_name": ""
        }

        if platform == "ANDROID":
            data["category"] = ANDROID_CATEGORIES
        elif platform == "IOS":
            data["category"] = IOS_CATEGORIES
        else:
            err_msg = f"无效平台: {platform}"
            logger.error(err_msg)
            return jsonify({"code": 400, "msg": err_msg}), 400

        logger.info("\n===== 发送给Mintegral的参数 =====")
        logger.info(json.dumps(data, ensure_ascii=False, indent=2))
        logger.info("===============================\n")

        headers = get_mintegral_headers()
        response = requests.post(
            MINTERGRAL_CAMPAIGN_URL,
            headers=headers,
            json=data,
            timeout=30
        )

        logger.info(f"创建广告响应: 状态码={response.status_code}, 内容={response.text}")

        if response.status_code == 200:
            try:
                result = response.json()
                if result.get('code') == 200:
                    return jsonify({
                        "code": 200,
                        "msg": "广告创建成功",
                        "data": {
                            "campaign_id": result['data'].get('campaign_id'),
                            "campaign_name": campaign_name[:100],
                            "platform": platform,
                            "creative_md5": creative_md5
                        }
                    })
                else:
                    return jsonify({
                        "code": result.get('code'),
                        "msg": f"API返回错误: {result.get('msg')}"
                    }), result.get('code')
            except json.JSONDecodeError:
                return jsonify({"code": 500, "msg": "API响应不是JSON格式"}), 500
        else:
            return jsonify({
                "code": response.status_code,
                "msg": f"API请求失败: 状态码={response.status_code}, 内容={response.text}"
            }), response.status_code

    except Exception as e:
        logger.error(f"创建广告异常: {str(e)}", exc_info=True)
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route('/api/search_campaigns', methods=['GET'])
def search_campaigns():
    try:
        search_term = request.args.get('search', '')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))

        # 构建Mintegral API查询参数
        params = {
            'page': page,
            'limit': limit
        }

        # 根据搜索词确定查询参数
        if search_term.isdigit():
            # 如果是数字，当作广告ID查询
            params['campaign_id'] = search_term
        elif '.' in search_term:
            # 如果包含点号，当作包名查询
            params['package_name'] = search_term
        else:
            # 否则当作广告名称查询
            params['campaign_name'] = search_term

        headers = get_mintegral_headers()
        response = requests.get(
            "https://ss-api.mintegral.com/api/open/v1/campaign",
            headers=headers,
            params=params,
            timeout=30
        )

        logger.info(f"广告查询响应: 状态码={response.status_code}, 内容={response.text}")

        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 200:
                # 处理返回的广告数据
                campaigns = []
                for item in result['data'].get('list', []):
                    campaigns.append({
                        "campaign_id": item.get('campaign_id'),
                        "campaign_name": item.get('campaign_name'),
                        "product_name": item.get('product_name'),
                        "package_name": item.get('package_name'),
                        "preview_url": item.get('preview_url'),
                        "platform": item.get('platform'),
                        "status": item.get('status'),
                        "description": item.get('description'),
                        "icon": item.get('icon'),
                        "category": item.get('category'),
                        "app_size": item.get('app_size'),
                        "min_version": item.get('min_version')
                    })

                return jsonify({
                    "code": 200,
                    "msg": "查询成功",
                    "data": {
                        "total": result['data'].get('total'),
                        "page": page,
                        "limit": limit,
                        "campaigns": campaigns
                    }
                })
            else:
                return jsonify({
                    "code": result.get('code'),
                    "msg": f"查询失败: {result.get('msg')}"
                }), result.get('code')
        else:
            return jsonify({
                "code": response.status_code,
                "msg": f"查询请求失败: {response.text}"
            }), response.status_code

    except Exception as e:
        logger.error(f"广告查询异常: {str(e)}", exc_info=True)
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route('/api/get_creative_sets', methods=['GET'])
def get_creative_sets():
    """查询创意组列表"""
    try:
        # 获取请求参数
        creative_set_name = request.args.get('creative_set_name')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))

        # 构建请求参数
        params = {
            'page': page,
            'limit': limit
        }
        if creative_set_name:
            params['creative_set_name'] = creative_set_name

        # 调用Mintegral API
        headers = get_mintegral_headers()
        response = requests.get(
            MINTERGRAL_CREATIVE_SETS_URL,
            headers=headers,
            params=params,
            timeout=30
        )

        logger.info(f"创意组查询响应: 状态码={response.status_code}, 内容={response.text}")

        # 处理响应
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 200:
                creative_sets = []
                creative_set_list = result['data'].get('list', [])
                # 收集所有offer_id，用于批量查询广告单元
                offer_ids = list(set(str(item.get('offer_id')) for item in creative_set_list if item.get('offer_id')))
                campaign_name_map = {}
                if offer_ids:
                    # 构建广告单元查询参数
                    offer_params = {
                        'offer_id': ','.join(offer_ids),
                        'limit': len(offer_ids)  # 确保获取所有
                    }

                    # 调用广告单元查询API
                    offer_response = requests.get(
                        "https://ss-api.mintegral.com/api/open/v1/offers",
                        headers=headers,
                        params=offer_params,
                        timeout=30
                    )

                    if offer_response.status_code == 200:
                        offer_result = offer_response.json()
                        if offer_result.get('code') == 200:
                            for offer in offer_result['data'].get('list', []):
                                campaign_name_map[offer.get('offer_id')] = offer.get('campaign_name', '未知广告活动')
                    else:
                        logger.error(f"广告单元查询失败: HTTP {offer_response.status_code}")

                # 构建创意组数据
                for item in creative_set_list:
                    offer_id = item.get('offer_id')
                    campaign_name = campaign_name_map.get(offer_id, '未知广告活动')

                    creative_sets.append({
                        "creative_set_id": item.get('creative_set_id'),
                        "creative_set_name": item.get('creative_set_name'),
                        "campaign_name": campaign_name,  # 添加广告活动名称
                        "combination_method": item.get('combination_method'),
                        "material_count": len(item.get('creatives', [])),
                        "ad_outputs": item.get('ad_outputs', []),
                        "offer_id": offer_id,
                        "geos": item.get('geos', []),
                        "creatives": item.get('creatives', []),
                        "created_at": item.get('created_at'),
                        "status": item.get('status')
                    })

                return jsonify({
                    "code": 200,
                    "msg": "查询成功",
                    "data": {
                        "total": result['data'].get('total'),
                        "page": page,
                        "limit": limit,
                        "creative_sets": creative_sets
                    }
                })
            else:
                return jsonify({
                    "code": result.get('code'),
                    "msg": f"查询失败: {result.get('msg')}"
                }), result.get('code')
        else:
            return jsonify({
                "code": response.status_code,
                "msg": f"查询请求失败: {response.text}"
            }), response.status_code

    except Exception as e:
        logger.error(f"创意组查询异常: {str(e)}", exc_info=True)
        return jsonify({"code": 500, "msg": str(e)}), 500


# 创建广告单元接口
def get_timezone_offset(tz_name):
    tz_map = {
        "Asia/Shanghai": 8.0,
        "UTC": 0.0,
        "America/New_York": -5.0,
        "Europe/London": 0.0,
        "Europe/Paris": 1.0,
        "Australia/Sydney": 10.0,
        "Asia/Tokyo": 9.0,
        "Asia/Seoul": 9.0,
        "Asia/Calcutta": 5.5,
        "America/Los_Angeles": -8.0
    }
    return tz_map.get(tz_name, 8.0)  # 默认使用东八区


@app.route('/api/create_offer', methods=['POST'])
def create_offer():
    try:
        logger.info("开始处理创建offer请求")

        # 解析请求数据
        data = request.json
        logger.debug(f"接收到的请求数据: {data}")

        campaign_id = data.get('campaign_id')
        creative_set_id = data.get('creative_set_id')
        offer_name = data.get('offer_name')
        bid_rate = data.get('bid_rate', 0.1)
        target_geo = data.get('target_geo', 'US')
        billing_type = data.get('billing_type', 'CPI')
        timezone_name = data.get('timezone', 'Asia/Shanghai')  # 时区名称

        # 广告展示类型：匹配MTG的target_ad_type（图片+视频全类型）

        target_ad_type = (
            "BANNER,"
            "MORE_OFFER,"
            "DISPLAY_INTERSTITIAL,"  # 全屏图片
            "DISPLAY_NATIVE,"  # 原生广告（包含横图、Icon等）
            "APPWALL,"  # 应用墙
            "SPLASH_AD,"  # 开屏广告
            "INTERSTITIAL_VIDEO,"  # 全屏视频
            "NATIVE_VIDEO,"  # 原生视频
            "INSTREAM_VIDEO,"  # 插播视频
            "REWARDED_VIDEO"  # 激励视频
        )

        # 验证必要参数
        if not all([campaign_id, creative_set_id, offer_name]):
            logger.warning("缺少必要参数")
            return jsonify({"code": 400, "msg": "缺少必要参数"}), 400

        # 强制转换ID为整数（MTG要求）
        try:
            campaign_id = int(campaign_id)
            creative_set_id = int(creative_set_id)
        except:
            logger.warning("ID必须为整数")
            return jsonify({"code": 400, "msg": "ID必须为整数"}), 400

        # 校验bid_rate格式
        try:
            bid_rate = float(bid_rate)
            if bid_rate <= 0:
                raise ValueError
        except:
            logger.warning("bid_rate必须为正数")
            return jsonify({"code": 400, "msg": "bid_rate必须为正数"}), 400

        # 校验offer_name格式（MTG允许字母+数字+下划线）
        if not re.match(r'^[a-zA-Z0-9_]{3,95}$', offer_name):
            logger.warning("offer_name格式错误")
            return jsonify({"code": 400, "msg": "offer_name格式错误"}), 400

        # 校验target_geo格式
        if not re.match(r'^[A-Z]{2}(,[A-Z]{2})*$', target_geo):
            logger.warning("target_geo格式错误")
            return jsonify({"code": 400, "msg": "target_geo格式错误"}), 400

        # 校验billing_type
        if billing_type not in ['CPI', 'CPC', 'CPM', 'CPA']:
            logger.warning("billing_type格式错误")
            return jsonify({"code": 400, "msg": "billing_type格式错误"}), 400

        # 查询创意组详情
        logger.info(f"查询创意组详情: creative_set_id={creative_set_id}")
        headers = get_mintegral_headers()
        detail_response = requests.get(
            MINTERGRAL_CREATIVE_SETS_URL,
            headers=headers,
            params={'creative_set_id': creative_set_id, 'page': 1, 'limit': 1},
            timeout=30
        )

        # 处理创意组查询HTTP错误
        if detail_response.status_code != 200:
            logger.error(f"创意组查询失败: HTTP {detail_response.status_code}")
            logger.debug(f"响应内容: {detail_response.text}")
            return jsonify({"code": 500, "msg": "创意组查询失败"}), 500

        # 解析创意组查询响应
        try:
            result = detail_response.json()
        except ValueError:
            logger.error("无法解析创意组查询响应")
            logger.debug(f"响应内容: {detail_response.text}")
            return jsonify({"code": 500, "msg": "无法解析创意组查询响应"}), 500

        if result.get('code') != 200 or not result['data'].get('list'):
            logger.warning(f"创意组不存在: code={result.get('code', 404)}")
            return jsonify({"code": 404, "msg": "创意组不存在"}), 404

        creative_set_detail = result['data']['list'][0]
        logger.info(f"成功获取创意组详情: {creative_set_detail.get('creative_set_name')}")

        # 创意类型映射字典 - 全英文名称
        # creative_type_mapping = {
        #     # 图片类 (111)
        #     "FULL_SCREEN_IMAGE": 111,  # 全屏图片
        #     "LANDSCAPE_IMAGE": 111,  # 横图
        #     "ICON": 111,  # Icon
        #     "BASIC_BANNER": 111,  # 基础横幅
        #     "IMAGE_BANNER": 111,  # 图片横幅
        #
        #     # 视频类 (211)
        #     "VIDEO_END_CARD": 211,  # 视频&图片结束卡片
        #     "VIDEO_PLAYABLE": 211,  # 视频&试玩广告
        #     "FULL_SCREEN_VIDEO": 211,  # 全屏视频
        #     "LARGE_VIDEO_BANNER": 211,  # 视频大横幅
        #     "SMALL_VIDEO_BANNER": 211,  # 视频小横幅
        #
        #     # HTML类 (311)
        #     "PLAYABLE_AD": 311,  # 试玩广告
        #
        #     # 通用类型（如果API返回这些）
        #     "VIDEO": 211,  # 视频类通用
        #     "IMAGE": 111,  # 图片类通用
        #     "PLAYABLE": 311  # HTML类通用
        # }
        creative_type_mapping = {
            # 图片类 (1xx)
            "FULL_SCREEN_IMAGE": 111,  # 全屏创意 - 全屏图片
            "DISPLAY_INTERSTITIAL": 111,  # 图片类插屏广告
            "BANNER": 121,  # 大横幅创意 - 横图
            "DISPLAY_NATIVE": 121,  # 原生图片广告
            "ICON": 122,  # 小横幅创意 - Icon
            "MORE_OFFER": 122,  # More Offer
            "APP_WALL": 122,  # App Wall
            "BASIC_BANNER": 131,  # 小横幅创意 - 基础横幅
            "IMAGE_BANNER": 132,  # 小横幅创意 - 图片横幅

            # 视频类 (2xx)
            "VIDEO_END_CARD": 211,  # 全屏创意 - 视频&图片结束卡片
            "SPLASH_AD": 211,  # 开屏广告
            "INTERSTITIAL_VIDEO": 211,  # 视频类插屏广告
            "REWARDED_VIDEO": 211,  # 激励视频广告
            "VIDEO_PLAYABLE": 212,  # 全屏创意 - 视频&试玩广告
            "FULL_SCREEN_VIDEO": 213,  # 全屏创意 - 全屏视频
            "NATIVE_VIDEO": 213,  # 原生视频广告
            "INSTREAM_VIDEO": 213,  # 流媒体视频广告
            "LARGE_VIDEO_BANNER": 221,  # 大横幅创意 - 视频大横幅
            "SMALL_VIDEO_BANNER": 231,  # 小横幅创意 - 视频小横幅

            # 通用类型（如果API返回这些）
            "VIDEO": 211,  # 视频类通用
            "IMAGE": 111,  # 图片类通用
            "PLAYABLE": 311,  # HTML类通用
            "PLAYABLE_AD": 311  # HTML类通用（同义词）
        }
        # 构建创意组
        creative_set = {
            "creative_set_name": creative_set_detail.get("creative_set_name"),
            "geos": ["ALL"],  # 使用广告单元级别的geo设置
            "ad_outputs": creative_set_detail.get("ad_outputs"),
            "creatives": [
                {
                    "creative_name": creative.get("creative_name"),
                    "creative_md5": creative.get("creative_md5"),
                    "creative_type": creative.get("creative_type"),
                    "dimension": creative.get("dimension"),

                }
                for creative in creative_set_detail.get("creatives", [])
            ]
        }

        # 检查是否有无效的创意类型
        if 0 in creative_set["ad_outputs"]:
            # 找出所有未知的创意类型
            unknown_types = set()
            for creative in creative_set_detail.get("creatives", []):
                creative_type = creative.get("creative_type")
                if creative_type not in creative_type_mapping:
                    unknown_types.add(creative_type)

            logger.warning(f"创意组中包含未知的创意类型: {', '.join(unknown_types)}")
            return jsonify({
                "code": 400,
                "msg": f"创意组中包含未知的创意类型: {', '.join(unknown_types)}",
                "unknown_types": list(unknown_types)
            }), 400

        if not creative_set["creatives"]:
            logger.warning("创意组中没有可用素材")
            return jsonify({"code": 400, "msg": "创意组中没有可用素材"}), 400

        # 计算一个月后的开始时间
        start_time = int(time.time()) + (30 * 24 * 60 * 60)  # 当前时间+30天

        # 获取时区偏移量
        promote_timezone = get_timezone_offset(timezone_name)

        # 构建请求体
        payload = {
            "campaign_id": campaign_id,
            "offer_name": offer_name,
            "daily_cap_type": "BUDGET",
            "daily_cap": 200,
            "promote_timezone": promote_timezone,  # 数字偏移量
            "start_time": start_time,  # 一个月后开始
            "target_geo": target_geo,  # 字符串，如"US"或"US,GB"
            "billing_type": billing_type,
            "bid_rate": str(bid_rate),  # 字符串类型
            "target_ad_type": target_ad_type,
            "creative_sets": [creative_set],  # 注意字段名是复数
            "network": "WIFI,2G,3G,4G,5G",  # 网络类型
            "target_device": "PHONE,TABLET",  # 设备类型
            "status": 1  # 1表示启用
        }

        logger.debug(f"最终请求体: {json.dumps(payload, indent=2)}")
        logger.info(f"准备创建offer: {offer_name}")

        # 发送创建offer请求
        create_response = requests.post(
            MINTERGRAL_CREATE_OFFER_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

        # 记录完整的响应信息
        logger.info(f"Mintegral API响应状态码: {create_response.status_code}")
        logger.info(f"Mintegral API响应内容: {create_response.text}")

        # 处理创建offer的HTTP错误
        if create_response.status_code != 200:
            logger.error(f"创建offer失败: HTTP {create_response.status_code}")

            # 尝试解析错误详情
            try:
                error_detail = create_response.json()
                logger.error(f"Mintegral API错误详情: {error_detail}")
            except:
                logger.error(f"无法解析错误响应: {create_response.text}")

            return jsonify({
                "code": 500,
                "msg": f"Mintegral API请求失败: HTTP {create_response.status_code}",
                "detail": create_response.text  # 返回原始错误内容
            }), 500

        # 解析创建offer的响应
        try:
            create_result = create_response.json()
        except ValueError:
            logger.error("无法解析创建offer的响应")
            logger.debug(f"响应内容: {create_response.text}")
            return jsonify({
                "code": 500,
                "msg": "无法解析创建offer的响应"
            }), 500

        # 处理业务错误
        if create_result.get('code') != 200:
            logger.error(f"Mintegral API业务错误: {create_result.get('msg', '未知错误')}")
            logger.debug(f"错误详情: {create_result}")
            return jsonify({
                "code": 500,
                "msg": f"Mintegral API业务错误: {create_result.get('msg', '未知错误')}",
                "detail": create_result
            }), 500

        logger.info(f"成功创建offer: offer_id={create_result.get('data', {}).get('offer_id')}")
        return jsonify({
            "code": 200,
            "msg": "创建offer成功",
            "data": create_result.get('data')
        }), 200

    except Exception as e:
        # 记录完整的错误堆栈
        logger.exception("处理请求时发生异常")
        return jsonify({
            "code": 500,
            "msg": f"服务器内部错误: {str(e)}"
        }), 500


@app.route('/api/get_offer_by_name', methods=['GET'])
def get_offer_by_name():
    """通过名称查询广告单元详情接口"""
    try:
        offer_name = request.args.get('offer_name')
        if not offer_name:
            return jsonify({"code": 400, "msg": "offer_name不能为空"}), 400

        logging.info(f"通过名称查询广告单元: {offer_name}")

        # 构建MTG API请求
        headers = get_mintegral_headers()
        params = {
            "offer_name": offer_name,
            "limit": 1,  # 只获取第一个匹配项
            "ext_fields": "bid_rate_by_mtgid,target_app"  # 获取扩展字段
        }

        # 发送请求到MTG API
        response = requests.get(
            f"{MINTERGRAL_API_URL}/offers",
            headers=headers,
            params=params,
            timeout=30
        )

        # 处理响应
        if response.status_code == 200:
            mtg_data = response.json()
            if mtg_data.get("code") == 200 and mtg_data['data']['list']:
                print(mtg_data)
                offer_detail = mtg_data['data']['list'][0]
                logging.info(f"成功获取广告单元详情: ID={offer_detail['offer_id']}")
                # print(offer_detail)
                return jsonify({
                    "code": 200,
                    "msg": "success",
                    "data": offer_detail
                })
            else:
                msg = mtg_data.get('msg', '未找到匹配的广告单元')
                logging.warning(f"未找到广告单元: {msg}")
                return jsonify({
                    "code": 404,
                    "msg": f"未找到名称为 '{offer_name}' 的广告单元"
                }), 404
        else:
            logging.error(f"MTG API请求失败: HTTP {response.status_code}")
            return jsonify({
                "code": 500,
                "msg": f"MTG API请求失败: HTTP {response.status_code}"
            }), 500

    except requests.exceptions.Timeout:
        logging.error("MTG API请求超时")
        return jsonify({
            "code": 504,
            "msg": "MTG API请求超时"
        }), 504
    except Exception as e:
        logging.exception("通过名称查询广告单元详情异常")
        return jsonify({
            "code": 500,
            "msg": f"服务器错误: {str(e)}"
        }), 500


MINTERGRAL_API_BASE = "https://ss-api.mintegral.com/api/v1"
def get_mintegralid_headers(FIXED_COOKIE):
    """生成Mintegral API请求头（使用固定Cookie）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Cookie": FIXED_COOKIE,
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Origin": "https://adv.mintegral.com",
        "Referer": "https://adv.mintegral.com/cn/offers"
    }
    return headers

@app.route('/api/fetch_ids', methods=['GET'])
def get_offer_material_ids():
    """获取广告单元的所有material IDs（只统计audit_status为2的material）"""
    try:
        offer_id = request.args.get('offer_id')
        FIXED_COOKIE = request.args.get('fixed_cookie')
        print(offer_id)
        print(FIXED_COOKIE)

        # 构建MTG API请求
        headers = get_mintegralid_headers(FIXED_COOKIE)

        # 发送请求到MTG API
        response = requests.get(
            f"{MINTERGRAL_API_BASE}/offers/{offer_id}",
            headers=headers,
            timeout=30
        )

        logger.info(f"API响应状态码: {response.status_code}")
        logger.info(f"API响应内容: {response.text}")

        # 处理响应
        if response.status_code == 200:
            mtg_data = response.json()

            if mtg_data.get("code") == 200:
                offer_detail = mtg_data.get('data', {})

                # 提取所有audit_status为2的material IDs
                material_ids = []
                creative_groups = offer_detail.get('creative_groups', [])

                for group in creative_groups:
                    materials = group.get('materials', [])
                    for material in materials:
                        # 只统计audit_status为2的material
                        if material.get('audit_status') == 2:

                            material_id = material.get('offer_material_id')
                            if material_id:
                                material_ids.append(material_id)
                                logger.info(
                                    f"找到audit_status=2的material: ID={material_id}, 名称={material.get('material_name')}")

                logger.info(f"成功提取 {len(material_ids)} 个audit_status=2的material IDs")
                print(material_ids)

                # 返回结果字典
                return {
                    "code": 200,
                    "msg": "success",
                    "data": {
                        "offer_id": offer_id,
                        "material_ids": material_ids,
                        "material_count": len(material_ids),
                        "audit_status": 2  # 添加审核状态标记
                    }
                }
            else:
                msg = mtg_data.get('msg', '未找到广告单元')
                logger.warning(f"未找到广告单元: {msg}")
                return {
                    "code": 404,
                    "msg": f"未找到ID为 '{offer_id}' 的广告单元"
                }
        else:
            logger.error(f"MTG API请求失败: HTTP {response.status_code}")
            return {
                "code": 500,
                "msg": f"MTG API请求失败: HTTP {response.status_code}"
            }

    except requests.exceptions.Timeout:
        logger.error("MTG API请求超时")
        return {
            "code": 504,
            "msg": "MTG API请求超时"
        }
    except Exception as e:
        logger.exception("获取失败")
        return {
            "code": 500,
            "msg": f"服务器错误: {str(e)}"
        }



@app.route('/api/add_to_blacklist', methods=['POST'])
def add_to_blacklist():
    """将流量源加入黑名单接口（支持多个MTGID）"""
    try:
        data = request.json
        offer_id = data.get('offer_id')
        additional_mtgids = data.get('additional_mtgids', '')  # 用户额外添加的MTGID

        # 验证参数
        if not offer_id:
            return jsonify({"code": 400, "msg": "offer_id不能为空"}), 400

        # 首先通过offer_id查询广告单元详情，获取target_app.mtg_id作为固定MTGID列表
        headers = get_mintegral_headers()
        params = {
            "offer_id": offer_id,
            "limit": 1,
            "ext_fields": "target_app"
        }

        # 发送请求到MTG API获取广告单元详情
        response = requests.get(
            f"{MINTERGRAL_API_URL}/offers",
            headers=headers,
            params=params,
            timeout=30
        )

        if response.status_code != 200:
            logging.error(f"获取广告单元详情失败: HTTP {response.status_code}")
            return jsonify({
                "code": 500,
                "msg": f"获取广告单元详情失败: HTTP {response.status_code}"
            }), 500

        mtg_data = response.json()
        if mtg_data.get("code") != 200 or not mtg_data['data']['list']:
            msg = mtg_data.get('msg', '未找到匹配的广告单元')
            logging.warning(f"未找到广告单元: {msg}")
            return jsonify({
                "code": 404,
                "msg": f"未找到ID为 '{offer_id}' 的广告单元"
            }), 404

        # 从广告单元详情中提取target_app.mtg_id作为固定MTGID列表
        offer_detail = mtg_data['data']['list'][0]
        fixed_mtgids = offer_detail.get('target_app', {}).get('mtg_id', []) if offer_detail.get('target_app') else []

        logging.info(f"从广告单元获取的固定MTGID: {fixed_mtgids}")

        # 合并固定MTGID和用户添加的MTGID
        all_mtgids = fixed_mtgids.copy()

        # 处理用户额外添加的MTGID
        additional_list = []
        if additional_mtgids:
            # 分割用户输入的MTGID（支持逗号分隔）
            additional_list = additional_mtgids.split(',')
            additional_list = [id.strip() for id in additional_list if id.strip()]

            # 去重并添加到总列表
            for mtgid in additional_list:
                if mtgid not in all_mtgids:
                    all_mtgids.append(mtgid)

        # 转换为逗号分隔的字符串
        mtgids_str = ','.join(all_mtgids)

        logging.info(f"添加流量到黑名单: offer_id={offer_id}, mtgids_count={len(all_mtgids)}")
        logging.debug(f"完整MTGID列表: {mtgids_str}")

        # 构建MTG API请求
        payload = {
            "offer_id": offer_id,
            "option": "DISABLE",
            "mtgid": mtgids_str
        }

        # 发送请求到MTG API
        response = requests.put(
            f"{MINTERGRAL_API_URL}/offer/target",
            headers=headers,
            json=payload,
            timeout=30
        )

        # 处理响应
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 200:
                logging.info("流量成功添加到黑名单")
                return jsonify({
                    "code": 200,
                    "msg": "流量成功添加到黑名单",
                    "fixed_count": len(fixed_mtgids),
                    "additional_count": len(additional_list),
                    "total_count": len(all_mtgids)
                })
            else:
                msg = result.get('msg', '添加黑名单失败')
                logging.error(f"MTG错误: {msg}")
                return jsonify({
                    "code": result.get("code", 500),
                    "msg": msg
                }), 400
        else:
            logging.error(f"MTG API请求失败: HTTP {response.status_code}")
            return jsonify({
                "code": 500,
                "msg": f"MTG API请求失败: HTTP {response.status_code}"
            }), 500

    except requests.exceptions.Timeout:
        logging.error("MTG API请求超时")
        return jsonify({
            "code": 504,
            "msg": "MTG API请求超时"
        }), 504
    except Exception as e:
        logging.exception("添加流量到黑名单异常")
        return jsonify({
            "code": 500,
            "msg": f"服务器错误: {str(e)}"
        }), 500


@app.route('/api/update_bid_rate', methods=['POST'])
def update_bid_rate():
    """更新广告单元出价接口"""
    try:
        data = request.json
        offer_id = data.get('offer_id')
        bid_rate = data.get('bid_rate')
        bid_rate_by_mtgid = data.get('bid_rate_by_mtgid', [])

        # 验证参数
        if not offer_id:
            return jsonify({"code": 400, "msg": "offer_id不能为空"}), 400

        # 修改验证逻辑：允许bid_rate_by_mtgid为空数组的情况
        if bid_rate is None and not bid_rate_by_mtgid:
            return jsonify({"code": 400, "msg": "必须提供默认出价或流量ID出价"}), 400

        # 构建请求体
        payload = {
            "offer_id": offer_id
        }

        if bid_rate is not None:
            payload["bid_rate"] = bid_rate

        # 修改逻辑：支持传递空数组来清空所有流量ID出价
        if bid_rate_by_mtgid is not None:  # 确保传入了bid_rate_by_mtgid
            if isinstance(bid_rate_by_mtgid, list) and not bid_rate_by_mtgid:
                # 明确设置为空数组表示删除所有流量ID出价
                payload["bid_rate_by_mtgid"] = []
            elif bid_rate_by_mtgid:
                # 验证并格式化出价设置
                valid_bid_rate_by_mtgid = []
                for item in bid_rate_by_mtgid:
                    if 'mtgid' in item and 'bid_rate' in item:
                        valid_item = {
                            "country_code": "US",  # 固定国家代码为US
                            "mtgid": item['mtgid'],
                            "bid_rate": item['bid_rate']
                        }
                        valid_bid_rate_by_mtgid.append(valid_item)

                if valid_bid_rate_by_mtgid:
                    payload["bid_rate_by_mtgid"] = valid_bid_rate_by_mtgid
                else:
                    return jsonify({
                        "code": 400,
                        "msg": "流量ID出价设置格式错误，应为{'mtgid': 'xx', 'bid_rate': xx}的数组"
                    }), 400

        logging.info(f"更新广告单元出价: offer_id={offer_id}, payload={payload}")

        # 构建MTG API请求头
        headers = get_mintegral_headers()

        # 发送请求到MTG API
        response = requests.put(
            f"{MINTERGRAL_API_URL}/offer/bid_rate",
            headers=headers,
            json=payload,
            timeout=30
        )

        # 处理响应
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 200:
                logging.info("出价更新成功")
                return jsonify({
                    "code": 200,
                    "msg": "出价更新成功"
                })
            else:
                msg = result.get('msg', '出价更新失败')
                logging.error(f"MTG错误: {msg}")
                return jsonify({
                    "code": result.get("code", 500),
                    "msg": msg
                }), 400
        else:
            logging.error(f"MTG API请求失败: HTTP {response.status_code}")
            return jsonify({
                "code": 500,
                "msg": f"MTG API请求失败: HTTP {response.status_code}"
            }), 500

    except requests.exceptions.Timeout:
        logging.error("MTG API请求超时")
        return jsonify({
            "code": 504,
            "msg": "MTG API请求超时"
        }), 504
    except Exception as e:
        logging.exception("更新出价异常")
        return jsonify({
            "code": 500,
            "msg": f"服务器错误: {str(e)}"
        }), 500


flask_port = None


def run_flask():
    global flask_port

    # 动态选择可用端口
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()

    flask_port = port  # 存储端口号

    logger.info(f"Starting Flask on port {port}")

    # 启动Flask
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)


def main():
    # 启动Flask服务器（子线程）
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # 等待端口分配完成
    while flask_port is None:
        time.sleep(0.1)

    # 启动PyWebView窗口，使用动态端口
    webview.create_window(
        title="ClickFlare 日志工具",
        url=f"http://127.0.0.1:{flask_port}",  # 使用动态端口
        width=1000,
        height=800,
        resizable=True
    )
    webview.start()


if __name__ == '__main__':
    main()
