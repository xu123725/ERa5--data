# ERA5 数据下载器（ERA5 Data Downloader）

一款基于 **PySide6** 的 Windows 桌面应用，用于 **ECMWF ERA5 / ERA5-Land 再分析资料的下载、数据处理与可视化**。界面全中文，采用蓝白卡片式主题。

## 功能特性

| 模块 | 说明 |
| --- | --- |
| 下载 | 通过 CDS API 下载 ERA5 / ERA5-Land 数据，支持气压层、单层、月平均、日统计等数据集；内置全球/中国及分省区域预设；任务队列串行下载、实时进度与彩色日志 |
| 数据处理 | netCDF 文件合并、按经纬度裁剪、导出 CSV |
| 绘图 | 空间分布图（可叠加 cartopy 海岸线/国界底图）、时间序列图、垂直剖面图；Matplotlib 工具栏与参数编辑界面已全面汉化 |
| 设置 | CDS API 地址与访问令牌管理，自动写入 `~/.cdsapirc` |
| 帮助 | 应用内集成 Markdown 帮助文档（左侧目录 + 搜索 + 滚动跟随） |

**界面亮点**
- 蓝白数据面板主题（卡片、描边/幽灵按钮分级、状态语义着色）
- 下载页功能区为可拖动、可悬浮的停靠子窗口布局
- 保存 PNG 支持自动裁剪四周留白

## 环境要求

- Windows 10/11（其他平台可运行但未验证）
- Python 3.10+
- 依赖见 [requirements.txt](requirements.txt)

## 安装与运行

```bash
# 1. 克隆或下载本项目后，进入项目目录
cd era5-downloader

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动
python main.py
```

> 注意：国内网络访问 CDS 可能较慢，下载大文件时请耐心等待。

## 配置 CDS API

1. 前往 [CDS 官网](https://cds.climate.copernicus.eu) 注册并登录；
2. 在个人中心生成自己的 API Key（`url` + `key`）；
3. 打开应用 **「设置」** 页，填入地址与令牌并保存；也可以手动创建 `%USERPROFILE%\.cdsapirc`：

```
url: https://cds.climate.copernicus.eu/api
key: 你的个人API Key
```

> **重要**：首次使用某个数据集时，需先在 CDS 网页登录并勾选同意该数据集的使用条款，否则请求会返回 403。
>
> 本项目**不内置任何 API 密钥**，请使用自己的账户凭据。

## 使用说明

1. **下载**：选择数据集 → 填写气象要素与参数 → 选择区域/时间 → 点击「添加任务」加入队列串行下载；
2. **数据处理**：合并多个 `.nc` → 按经纬度裁剪 → 转为 CSV；
3. **绘图**：打开下载的 `.nc` 文件，选择变量与图型（空间分布/时间序列/垂直剖面），一键绘图并保存 PNG；
4. **帮助**：查看内置的 ERA5 再分析资料绘图帮助文档。

## 打包为 Windows exe

项目根目录运行：

```bat
build.bat
```

使用 PyInstaller 打包（已配置 `--collect-data` 收集 cartopy/matplotlib 数据、排除 PyQt5 避免多 Qt 绑定冲突），产物位于 `dist\ERA5下载器.exe`。体积较大（约 700MB，含绘图依赖库数据）属正常现象。

## 技术栈

PySide6 · matplotlib · cartopy · xarray · netCDF4 · cdsapi · PyInstaller

## 目录结构

```
├── main.py                  # 程序入口
├── app/
│   ├── api/cds_client.py    # CDS 请求构建与串行下载队列
│   ├── core/                # 配置、数据集预设、数据处理、绘图核心
│   ├── ui/                  # 下载/数据处理/绘图/设置/帮助 五个页签
│   └── resources/           # 蓝白主题 QSS 与帮助文档
├── build.bat                # PyInstaller 打包脚本
└── requirements.txt
```

## 数据与隐私

- 下载的数据文件（`.nc`/`.grib`）、导出的图片与日志均保存在用户选择的目录，不会上传；
- API 密钥仅保存在本地 `~/.cdsapirc`，请勿泄露。

## 许可

本项目仅用于学习与交流。
