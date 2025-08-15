# WCAG Contrast Checker

## Overview
WCAG Contrast Checker is a tool that evaluates web pages for compliance with WCAG 1.4.3 (Contrast Minimum) and WCAG 1.4.6 (Contrast Enhanced) accessibility requirements. This tool automatically detects all text elements on a webpage, calculates the contrast ratio between foreground and background colors, and determines compliance with WCAG guidelines based on font size, weight, and language.

## Installation
1. Clone the repository:
   ```
   git clone https://github.com/daishir0/wcag_contrast_checker
   cd wcag_contrast_checker
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Install Chrome/Chromium browser if not already installed.

4. Download the appropriate ChromeDriver for your Chrome version from [ChromeDriver website](https://chromedriver.chromium.org/downloads).

5. Create a `config.py` file with the following content:
   ```python
   ANTHROPIC_API_KEY = "your_anthropic_api_key"  # Optional for basic functionality
   CHROME_BINARY_PATH = "/path/to/chrome"  # e.g., "/usr/bin/google-chrome"
   CHROME_DRIVER_PATH = "/path/to/chromedriver"  # e.g., "/usr/local/bin/chromedriver"
   DEBUG = False  # Set to True for verbose output
   ```

## Usage
Run the tool by providing a URL to check:
```
python wcag_contrast_checker.py https://example.com
```

The tool will:
1. Open the webpage in a headless Chrome browser
2. Extract all visible text elements from the page
3. Filter out excluded elements (inactive UI, decorative text, logos, image text)
4. Calculate contrast ratios using WCAG-compliant luminance formulas
5. Apply language-specific and font-specific criteria
6. Generate a detailed report showing:
   - Total number of text elements analyzed
   - Elements with adequate contrast ratios
   - Elements with inadequate contrast ratios
   - Overall WCAG 1.4.3/1.4.6 compliance status
   - Detailed breakdown by situation (A/B) and language

## WCAG Compliance Criteria

### Situation A (Normal Text)
- **Required contrast ratio**: 4.5:1 or higher
- **Applies to**: Small text with normal font weight

### Situation B (Large Text)
- **Required contrast ratio**: 3:1 or higher
- **Applies to**: Large text or bold text

### Font Size Criteria

#### Japanese Text
- **Large text (bold)**: 18pt or larger, or 22pt or larger (normal weight)
- **Large text (normal)**: 14pt or larger, or 18pt or larger
- **Normal text**: All other sizes

#### English Text
- **Large text (bold)**: 18pt or larger, or 22pt or larger (normal weight)
- **Large text (normal)**: 14pt or larger, or 18pt or larger
- **Normal text**: All other sizes

## Excluded Elements
The following types of text are automatically excluded from analysis:
- Inactive UI components (disabled elements)
- Purely decorative text (aria-hidden="true")
- Logo and brand text
- Text that is part of images

## Technical Details

### Color Analysis
- Extracts RGB values from computed CSS styles
- Converts to relative luminance using WCAG formulas
- Calculates contrast ratio: (L1 + 0.05) / (L2 + 0.05)
- Supports both RGB and hex color formats

### Language Detection
- Automatically detects text language from HTML lang attributes
- Applies appropriate font size criteria for Japanese vs. English text
- Falls back to English criteria if language cannot be determined

### Font Analysis
- Extracts font-size and font-weight from computed styles
- Converts pixel measurements to points (approximate)
- Determines bold text (font-weight >= 700)

## Output Format
The tool provides detailed console output including:
- Summary statistics (total elements, compliance rate)
- Non-compliant elements with specific recommendations
- Compliant elements breakdown by situation
- Language-specific analysis results

## Notes
- The tool runs in headless mode for server environments
- Temporary Chrome data directories are automatically cleaned up
- The Anthropic API key is optional for basic contrast ratio calculations
- Processing time depends on the number of text elements on the page
- Ensure ChromeDriver version matches your Chrome browser version

## License
This project is licensed under the MIT License - see the LICENSE file for details.

---

# WCAG コントラスト比チェッカー

## 概要
WCAG コントラスト比チェッカーは、ウェブページがWCAG 1.4.3（コントラスト最小）およびWCAG 1.4.6（コントラスト強化）アクセシビリティ要件に準拠しているかを評価するツールです。このツールは、ウェブページ上のすべてのテキスト要素を自動的に検出し、前景色と背景色のコントラスト比を計算し、フォントサイズ、ウェイト、言語に基づいてWCAGガイドラインへの準拠を判定します。

## インストール方法
1. リポジトリをクローンします：
   ```
   git clone https://github.com/daishir0/wcag_contrast_checker
   cd wcag_contrast_checker
   ```

2. 必要な依存関係をインストールします：
   ```
   pip install -r requirements.txt
   ```

3. Chrome/Chromiumブラウザがインストールされていない場合はインストールします。

4. お使いのChromeバージョンに適合するChromeDriverを[ChromeDriverウェブサイト](https://chromedriver.chromium.org/downloads)からダウンロードします。

5. 以下の内容で`config.py`ファイルを作成します：
   ```python
   ANTHROPIC_API_KEY = "あなたのAnthropic APIキー"  # 基本機能には不要
   CHROME_BINARY_PATH = "/Chromeへのパス"  # 例："/usr/bin/google-chrome"
   CHROME_DRIVER_PATH = "/ChromeDriverへのパス"  # 例："/usr/local/bin/chromedriver"
   DEBUG = False  # 詳細な出力が必要な場合はTrueに設定
   ```

## 使い方
チェックするURLを指定してツールを実行します：
```
python wcag_contrast_checker.py https://example.com
```

このツールは以下を行います：
1. ヘッドレスChromeブラウザでウェブページを開く
2. ページからすべての可視テキスト要素を抽出
3. 除外対象要素をフィルタリング（非アクティブUI、装飾テキスト、ロゴ、画像テキスト）
4. WCAG準拠の輝度計算式を使用してコントラスト比を計算
5. 言語固有およびフォント固有の基準を適用
6. 詳細なレポートを生成：
   - 分析されたテキスト要素の総数
   - 適切なコントラスト比の要素
   - 不適切なコントラスト比の要素
   - WCAG 1.4.3/1.4.6への全体的な準拠状況
   - 状況（A/B）および言語別の詳細な内訳

## WCAG準拠基準

### 状況A（通常テキスト）
- **必要なコントラスト比**: 4.5:1以上
- **適用対象**: 小さなテキスト、通常のフォントウェイト

### 状況B（大きなテキスト）
- **必要なコントラスト比**: 3:1以上
- **適用対象**: 大きなテキストまたは太字テキスト

### フォントサイズ基準

#### 日本語テキスト
- **大きなテキスト（太字）**: 18pt以上、または22pt以上（通常ウェイト）
- **大きなテキスト（通常）**: 14pt以上、または18pt以上
- **通常テキスト**: 上記以外のサイズ

#### 英語テキスト
- **大きなテキスト（太字）**: 18pt以上、または22pt以上（通常ウェイト）
- **大きなテキスト（通常）**: 14pt以上、または18pt以上
- **通常テキスト**: 上記以外のサイズ

## 除外要素
以下のタイプのテキストは分析から自動的に除外されます：
- 非アクティブUIコンポーネント（無効化された要素）
- 純粋な装飾テキスト（aria-hidden="true"）
- ロゴおよびブランドテキスト
- 画像の一部であるテキスト

## 技術詳細

### 色分析
- 計算されたCSSスタイルからRGB値を抽出
- WCAG計算式を使用して相対輝度に変換
- コントラスト比を計算：(L1 + 0.05) / (L2 + 0.05)
- RGBおよび16進数カラー形式の両方をサポート

### 言語検出
- HTML lang属性からテキスト言語を自動検出
- 日本語対英語テキストに適切なフォントサイズ基準を適用
- 言語が判定できない場合は英語基準にフォールバック

### フォント分析
- 計算されたスタイルからfont-sizeとfont-weightを抽出
- ピクセル測定をポイントに変換（概算）
- 太字テキストを判定（font-weight >= 700）

## 出力形式
ツールは以下を含む詳細なコンソール出力を提供します：
- 統計サマリー（総要素数、準拠率）
- 具体的な推奨事項を含む非準拠要素
- 状況別の準拠要素の内訳
- 言語固有の分析結果

## 注意点
- ツールはサーバー環境向けにヘッドレスモードで実行されます
- Chrome一時データディレクトリは自動的にクリーンアップされます
- Anthropic APIキーは基本的なコントラスト比計算には不要です
- 処理時間はページ上のテキスト要素数に依存します
- ChromeDriverのバージョンがお使いのChromeブラウザのバージョンと一致していることを確認してください

## ライセンス
このプロジェクトはMITライセンスの下でライセンスされています。詳細はLICENSEファイルを参照してください。