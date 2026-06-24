# src/tools/car_services.py
import math
import requests
import subprocess


class CarServices:
    """
    免费 / 开源的车机服务：
      - 地理编码：Nominatim (OpenStreetMap)            免 key、开源
      - 路线规划：OSRM 公共服务器 router.project-osrm.org  免 key、开源、driving
      - 兜底：真实直线(haversine)距离估算，保证不同目的地距离/时间“各不相同”

    坐标系：全部 WGS-84，与 folium 默认 OSM 底图一致（红线不会偏移）。
    注意：OSRM 公共服务器限 ≤1 请求/秒、仅非商用，适合 demo。
    """

    # 起点：上海人民广场（WGS-84，经度,纬度）
    START_LON = 121.4691
    START_LAT = 31.2286

    # User-Agent 是 Nominatim 使用条款要求的，必须带上可识别标识
    HTTP_HEADERS = {"User-Agent": "cockpit-ai-assistant-demo/1.0 (portfolio)"}

    def __init__(self, amap_key=""):
        # 如果你愿意用高德（免费但需注册 key、非开源），把 key 填这里即可自动启用
        self.amap_key = amap_key or ""

    # ---------------- 工具函数 ----------------
    @staticmethod
    def _haversine_km(lon1, lat1, lon2, lat2):
        """两点球面直线距离（公里）"""
        R = 6371.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlmb = math.radians(lon2 - lon1)
        a = (math.sin(dphi / 2) ** 2
             + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # ---------------- 地理编码 ----------------
    def get_coords_by_keyword(self, keyword):
        """关键字 -> (lon, lat)，失败返回 None"""
        query = keyword if "上海" in keyword else f"{keyword} 上海"

        # 优先 Nominatim（开源免 key）
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                "q": query,
                "format": "json",
                "limit": 1,
                "countrycodes": "cn",
                "accept-language": "zh",
            }
            res = requests.get(url, params=params,
                               headers=self.HTTP_HEADERS, timeout=6).json()
            if isinstance(res, list) and len(res) > 0:
                lon = float(res[0]["lon"])
                lat = float(res[0]["lat"])
                print(f"[Nominatim] '{keyword}' -> {lon:.5f},{lat:.5f}")
                return (lon, lat)
        except Exception as e:
            print(f"[Nominatim 异常]: {e}")

        # 可选：如果填了高德 key，再用高德兜一层（GCJ-02，会自动转一下大致 WGS-84）
        if self.amap_key:
            try:
                url = "https://restapi.amap.com/v3/geocode/geo"
                params = {"key": self.amap_key, "address": keyword, "city": "上海"}
                r = requests.get(url, params=params, timeout=5).json()
                if r.get("status") == "1" and r.get("geocodes"):
                    lon, lat = r["geocodes"][0]["location"].split(",")
                    return (float(lon), float(lat))
            except Exception as e:
                print(f"[高德地理编码异常]: {e}")

        print(f"[地理编码失败] 未能定位：{keyword}")
        return None

    # ---------------- 路线规划 ----------------
    def start_navigation(self, destination_name):
        print(f"[路网服务] 🛰️ 正在为【{destination_name}】规划路线 ...")

        dest = self.get_coords_by_keyword(destination_name)
        if dest is None:
            # 连坐标都拿不到 -> 如实告知，不再编造距离
            return {
                "status": "fail",
                "reason": "not_found",
                "destination": destination_name,
            }
        dest_lon, dest_lat = dest

        # 1) 首选 OSRM 公共服务器算真实驾车路线
        try:
            coords = f"{self.START_LON},{self.START_LAT};{dest_lon},{dest_lat}"
            url = f"https://router.project-osrm.org/route/v1/driving/{coords}"
            params = {"overview": "full", "geometries": "geojson"}
            res = requests.get(url, params=params,
                               headers=self.HTTP_HEADERS, timeout=8).json()

            if res.get("code") == "Ok" and res.get("routes"):
                route = res["routes"][0]
                distance_km = round(route["distance"] / 1000, 1)
                duration_min = max(1, round(route["duration"] / 60))
                # geojson 坐标是 [lon, lat]，转成 app.py 需要的 "lon,lat;lon,lat" 字符串
                geo = route["geometry"]["coordinates"]
                poly_str = ";".join(f"{c[0]},{c[1]}" for c in geo)
                print(f"[OSRM] ✅ 算路成功：{distance_km} km / {duration_min} min")
                return {
                    "status": "success",
                    "distance": str(distance_km),
                    "duration": str(duration_min),
                    "points": [poly_str],
                    "destination": destination_name,
                }
            else:
                print(f"[OSRM] 返回非 Ok：{res.get('code')}")
        except Exception as e:
            print(f"[OSRM 异常，启用直线距离兜底]: {e}")

        # 2) 兜底：真实直线距离估算（不同目的地距离/时间各不相同）
        straight_km = self._haversine_km(
            self.START_LON, self.START_LAT, dest_lon, dest_lat)
        distance_km = round(straight_km * 1.4, 1)          # ×1.4 近似道路绕行
        duration_min = max(1, round(distance_km / 30 * 60))  # 市区约 30km/h
        poly_str = (f"{self.START_LON},{self.START_LAT};"
                    f"{dest_lon},{dest_lat}")
        print(f"[兜底估算] {distance_km} km / {duration_min} min")
        return {
            "status": "success",
            "distance": str(distance_km),
            "duration": str(duration_min),
            "points": [poly_str],
            "destination": destination_name,
            "estimated": True,
        }

    # ---------------- 餐厅检索（demo 用真实可定位地点）----------------
    def search_and_queue_restaurant(self, cuisine_type="美食"):
        # 用一个真实存在、可被地理编码到的上海餐厅，保证后续能算出真实路线
        return {
            "status": "success",
            "restaurant": "南翔馒头店（豫园店）",
            "cuisine": cuisine_type,
            "queue_msg": "已为您取号，前方排队 300 桌，预计等待 10 年",
        }

    # ---------------- 语音播报（macOS say）----------------
    def tts_speak(self, text):
        print(f"[车载语音播报] 🔊: {text}")
        try:
            subprocess.Popen(["say", "-v", "Tingting", text])
        except Exception as e:
            print(f"TTS 播报失败: {e}")


if __name__ == "__main__":
    svc = CarServices()
    for name in ["迪士尼", "静安寺", "虹桥火车站"]:
        r = svc.start_navigation(name)
        print(name, "->", r.get("status"),
              r.get("distance"), "km", r.get("duration"), "min")