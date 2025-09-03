#!/usr/bin/env python3
"""
Background Color Detection Verification Tool
============================================
5つの異なる背景色検出アルゴリズムを検証・比較するツール
"""

import sys
import time
import numpy as np
import cv2
from PIL import Image
from io import BytesIO
import math
from sklearn.cluster import KMeans
from collections import Counter
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config import CHROME_BINARY_PATH, CHROME_DRIVER_PATH, DEBUG
import re
import tempfile
import shutil
import os

def setup_driver():
    """WebDriverセットアップ"""
    options = Options()
    options.binary_location = CHROME_BINARY_PATH
    options.add_argument("--window-size=1366,768")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-infobars')
    options.add_argument('--headless=new')
    
    temp_dir = tempfile.mkdtemp()
    options.add_argument(f'--user-data-dir={temp_dir}')
    
    service = Service(executable_path=CHROME_DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    return driver, temp_dir

def cleanup_temp_dir(temp_dir):
    """一時ディレクトリクリーンアップ"""
    try:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        print(f"Warning: {e}")

def capture_element_by_xpath(driver, xpath):
    """指定されたXPathの要素のスクリーンショットを撮影"""
    try:
        element = driver.find_element(By.XPATH, xpath)
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", element)
        time.sleep(1)
        
        element_png = element.screenshot_as_png
        image = Image.open(BytesIO(element_png))
        return image, element
    except Exception as e:
        print(f"要素取得エラー: {e}")
        return None, None

def get_element_text_color(driver, element):
    """要素のテキスト色を取得"""
    try:
        color_str = driver.execute_script("return window.getComputedStyle(arguments[0]).color;", element)
        rgb_match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*[\d.]+)?\)', color_str)
        if rgb_match:
            return (int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3)))
        return (0, 0, 0)  # デフォルト黒
    except:
        return (0, 0, 0)

def create_enhanced_text_mask(image_array, text_color_rgb, threshold=40):
    """強化されたテキストマスクを作成"""
    text_color = np.array(text_color_rgb)
    distances = np.linalg.norm(image_array - text_color, axis=2)
    return distances <= threshold

def is_background_pixel(pixel, text_color_rgb, threshold=40):
    """ピクセルが背景かどうかを判定"""
    distance = np.linalg.norm(np.array(pixel) - np.array(text_color_rgb))
    return distance > threshold

# ============================================
# 案1: ドミナント・クラスタリング方式
# ============================================
def method1_dominant_clustering(image, text_color_rgb):
    """K-meansクラスタリングで主要背景色を検出"""
    try:
        image_array = np.array(image)
        h, w, c = image_array.shape
        
        # テキスト領域を強力に除去
        text_mask = create_enhanced_text_mask(image_array, text_color_rgb, threshold=50)
        background_pixels = image_array[~text_mask].reshape(-1, 3)
        
        if len(background_pixels) < 10:
            return None
        
        # K-meansで背景を4クラスターに分離
        n_clusters = min(4, len(background_pixels))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        clusters = kmeans.fit(background_pixels)
        
        # 最大クラスターを主要背景色として採用
        labels_count = np.bincount(clusters.labels_)
        largest_cluster_idx = np.argmax(labels_count)
        dominant_bg_color = clusters.cluster_centers_[largest_cluster_idx]
        
        return tuple(int(x) for x in dominant_bg_color)
    except Exception as e:
        print(f"Method1 error: {e}")
        return None

# ============================================
# 案2: 空間重み付き方式
# ============================================
def method2_spatial_weighted(image, text_color_rgb):
    """要素の中央部分により重みを付けた背景色計算"""
    try:
        image_array = np.array(image)
        h, w, c = image_array.shape
        
        # 距離マップ作成（中央からの距離）
        center_y, center_x = h // 2, w // 2
        y_coords, x_coords = np.ogrid[:h, :w]
        distance_map = np.sqrt((y_coords - center_y)**2 + (x_coords - center_x)**2)
        
        # 中央に近いほど重みが高い（ガウシアン重み）
        max_distance = np.sqrt(center_y**2 + center_x**2)
        if max_distance > 0:
            weights = np.exp(-2 * (distance_map / max_distance)**2)
        else:
            weights = np.ones((h, w))
        
        # テキスト領域を除外
        text_mask = create_enhanced_text_mask(image_array, text_color_rgb, threshold=45)
        
        # 背景ピクセルとその重みを取得
        background_mask = ~text_mask
        if np.sum(background_mask) == 0:
            return None
        
        background_pixels = image_array[background_mask]
        pixel_weights = weights[background_mask]
        
        # 重み付き平均で背景色を算出
        weighted_bg = np.average(background_pixels, axis=0, weights=pixel_weights)
        
        return tuple(int(x) for x in weighted_bg)
    except Exception as e:
        print(f"Method2 error: {e}")
        return None

# ============================================
# 案3: エッジ除外・コア領域方式
# ============================================
def method3_core_region(image, text_color_rgb):
    """エッジを除外してコア領域の背景色を計算"""
    try:
        image_array = np.array(image)
        
        # エッジ検出とマスク作成
        gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        
        # エッジから一定距離の領域を除外
        kernel = np.ones((5, 5), np.uint8)
        edge_dilated = cv2.dilate(edges, kernel, iterations=2)
        
        # テキスト領域も除外
        text_mask = create_enhanced_text_mask(image_array, text_color_rgb, threshold=45)
        
        # コア領域（エッジでもテキストでもない領域）
        core_mask = ~(edge_dilated.astype(bool) | text_mask)
        
        if np.sum(core_mask) == 0:
            return None
        
        core_pixels = image_array[core_mask]
        
        # コア領域の中央値を採用（外れ値に強い）
        bg_color = np.median(core_pixels, axis=0)
        
        return tuple(int(x) for x in bg_color)
    except Exception as e:
        print(f"Method3 error: {e}")
        return None

# ============================================
# 案4: 多重サンプリング方式
# ============================================
def method4_multi_sampling(image, text_color_rgb):
    """複数手法の結果を統合"""
    try:
        image_array = np.array(image)
        h, w, c = image_array.shape
        all_samples = []
        
        # 方法1: グリッドサンプリング
        grid_step_y = max(1, h // 8)
        grid_step_x = max(1, w // 8)
        for y in range(h//4, 3*h//4, grid_step_y):
            for x in range(w//4, 3*w//4, grid_step_x):
                if 0 <= y < h and 0 <= x < w:
                    if is_background_pixel(image_array[y, x], text_color_rgb, threshold=45):
                        all_samples.append(image_array[y, x])
        
        # 方法2: ランダムサンプリング
        np.random.seed(42)  # 再現性のため
        for _ in range(100):
            y, x = np.random.randint(0, h), np.random.randint(0, w)
            if is_background_pixel(image_array[y, x], text_color_rgb, threshold=45):
                all_samples.append(image_array[y, x])
        
        # 方法3: 中心円サンプリング
        cy, cx = h//2, w//2
        radius = min(h, w) // 4
        if radius > 0:
            for angle in np.linspace(0, 2*np.pi, 16):
                y = int(cy + radius * np.sin(angle))
                x = int(cx + radius * np.cos(angle))
                if 0 <= y < h and 0 <= x < w:
                    if is_background_pixel(image_array[y, x], text_color_rgb, threshold=45):
                        all_samples.append(image_array[y, x])
        
        if len(all_samples) == 0:
            return None
        
        all_samples = np.array(all_samples)
        
        # RGB各チャンネルで中央値を計算（最頻値の代替）
        bg_color = []
        for channel in range(3):
            median_value = np.median(all_samples[:, channel])
            bg_color.append(int(median_value))
        
        return tuple(bg_color)
    except Exception as e:
        print(f"Method4 error: {e}")
        return None

# ============================================
# 案5: 階層的背景検出方式
# ============================================
def get_dominant_color_from_hist(hist_3d, edges):
    """3Dヒストグラムから支配的な色を取得"""
    # 最大頻度のビンを見つける
    max_bin_idx = np.unravel_index(np.argmax(hist_3d), hist_3d.shape)
    
    # ビンの中心座標を計算
    r_center = (edges[0][max_bin_idx[0]] + edges[0][max_bin_idx[0] + 1]) / 2
    g_center = (edges[1][max_bin_idx[1]] + edges[1][max_bin_idx[1] + 1]) / 2
    b_center = (edges[2][max_bin_idx[2]] + edges[2][max_bin_idx[2] + 1]) / 2
    
    return (int(r_center), int(g_center), int(b_center))

def exclude_text_pixels(image_array, text_color_rgb, threshold=40):
    """テキストピクセルを除外"""
    text_mask = create_enhanced_text_mask(image_array, text_color_rgb, threshold)
    return image_array[~text_mask].reshape(-1, 3)

def calculate_confidence(bg_color, image_array):
    """背景色の信頼性スコアを計算"""
    if bg_color is None:
        return 0.0
    
    # 画像内でその色に近いピクセルの割合を信頼性とする
    pixels = image_array.reshape(-1, 3)
    distances = np.linalg.norm(pixels - np.array(bg_color), axis=1)
    similar_pixels = np.sum(distances < 30)
    confidence = similar_pixels / len(pixels)
    
    return confidence

def method5_hierarchical(image, text_color_rgb):
    """階層的に背景を分析"""
    try:
        image_array = np.array(image)
        
        # Level 1: 粗い分析（全体の色分布）
        pixels = image_array.reshape(-1, 3)
        hist_3d, edges = np.histogramdd(pixels, bins=(16, 16, 16), range=[(0, 255), (0, 255), (0, 255)])
        coarse_bg = get_dominant_color_from_hist(hist_3d, edges)
        
        # Level 2: テキスト除外後の分析
        text_excluded = exclude_text_pixels(image_array, text_color_rgb, threshold=40)
        if len(text_excluded) > 100:
            medium_bg = tuple(int(x) for x in np.mean(text_excluded, axis=0))
        else:
            medium_bg = coarse_bg
        
        # Level 3: 精密分析（エッジ・ノイズ除外）
        clean_bg = method3_core_region(image, text_color_rgb)
        if clean_bg is None:
            clean_bg = medium_bg
        
        # 階層的統合：精密→中間→粗いの順で信頼性判定
        confidence_scores = [
            calculate_confidence(clean_bg, image_array),
            calculate_confidence(medium_bg, image_array), 
            calculate_confidence(coarse_bg, image_array)
        ]
        
        best_method = np.argmax(confidence_scores)
        final_bg = [clean_bg, medium_bg, coarse_bg][best_method]
        
        return final_bg
    except Exception as e:
        print(f"Method5 error: {e}")
        return None

def rgb_to_hex(rgb):
    """RGBをHEX形式に変換"""
    if rgb is None:
        return None
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

def calculate_color_distance(color1, color2):
    """2つの色の距離を計算"""
    if color1 is None or color2 is None:
        return float('inf')
    return np.linalg.norm(np.array(color1) - np.array(color2))

def verify_background_detection(url, xpath, human_judgment_hex):
    """背景検出アルゴリズムを検証"""
    print(f"=== 背景色検出検証 ===")
    print(f"URL: {url}")
    print(f"XPath: {xpath}")
    print(f"人間判定: {human_judgment_hex}")
    
    # 人間判定をRGBに変換
    human_rgb = tuple(int(human_judgment_hex[i:i+2], 16) for i in (1, 3, 5))
    print(f"人間判定RGB: {human_rgb}")
    
    try:
        driver, temp_dir = setup_driver()
        driver.get(url)
        
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # 要素を取得
        image, element = capture_element_by_xpath(driver, xpath)
        if image is None:
            print("要素の取得に失敗しました")
            return
        
        # テキスト色を取得
        text_color = get_element_text_color(driver, element)
        print(f"テキスト色: {text_color}")
        
        # 各手法で背景色を計算
        methods = {
            "案1_ドミナント・クラスタリング": method1_dominant_clustering,
            "案2_空間重み付き": method2_spatial_weighted, 
            "案3_エッジ除外・コア領域": method3_core_region,
            "案4_多重サンプリング": method4_multi_sampling,
            "案5_階層的背景検出": method5_hierarchical
        }
        
        results = []
        
        print(f"\n=== 各手法の結果 ===")
        for method_name, method_func in methods.items():
            bg_color = method_func(image, text_color)
            hex_color = rgb_to_hex(bg_color)
            distance = calculate_color_distance(bg_color, human_rgb)
            
            print(f"{method_name}:")
            print(f"  RGB: {bg_color}")
            print(f"  HEX: {hex_color}")
            print(f"  人間判定との距離: {distance:.2f}")
            print()
            
            results.append({
                'method': method_name,
                'rgb': bg_color,
                'hex': hex_color,
                'distance': distance
            })
        
        # 人間判定に近い順にソート
        results.sort(key=lambda x: x['distance'])
        
        print(f"=== 人間判定に近い順ランキング ===")
        print(f"基準: {human_judgment_hex} {human_rgb}")
        print("-" * 50)
        
        for i, result in enumerate(results, 1):
            print(f"{i}位: {result['method']}")
            print(f"     結果: {result['hex']} {result['rgb']}")
            print(f"     差異: {result['distance']:.2f}")
            print()
        
        return results
        
    finally:
        driver.quit()
        cleanup_temp_dir(temp_dir)

def main():
    if len(sys.argv) != 4:
        print("Usage: python background_verification.py <URL> <XPath> <Human_Judgment_Hex>")
        print("Example: python background_verification.py https://info-fujino.com/ '/html/body/div[2]/main[1]/section[3]/div[1]/div[1]/div[1]/div[1]/h2[1]' '#E3E0E0'")
        sys.exit(1)
    
    url = sys.argv[1]
    xpath = sys.argv[2] 
    human_hex = sys.argv[3]
    
    if not human_hex.startswith('#') or len(human_hex) != 7:
        print("人間判定の色は#RRGGBBの形式で指定してください")
        sys.exit(1)
    
    verify_background_detection(url, xpath, human_hex)

if __name__ == "__main__":
    main()