# ERA5 再分析资料绘图帮助文档

**什么气象资料适合画什么图：空间分布图、时间序列图、垂直剖面图的资料选择与制图方法**

**报告日期：2026-08-13**

## 摘要

本文面向使用 ECMWF 第五代再分析资料 ERA5 开展气象绘图的用户，系统回答"什么样的气象资料适合画什么样的图"这一核心问题。ERA5 按垂直组织方式分为单层次与气压层（另有 137 层模式层）两大产品线：单层次数据描述地表与近地面二维状态，适合空间分布图与时间序列图；气压层数据构成三维场，既可取单层绘制空间分布图，也可沿垂直方向切开绘制剖面图。空间分布图的资料选择逻辑是：单层次变量（2m 气温、海平面气压、降水、10m 风）直接成图，气压层变量（500 hPa 位势、850 hPa 温度、各层风场）需先选定层次，图形要素以填色图、等值线图、风矢量三类为基础并常叠加使用；时间序列图适用于任意变量的单点或区域平均演变，但用于数十年尺度趋势研究时必须警惕观测系统变迁引入的非均一性误差——已有研究指出 ERA5 降水虚假趋势导致陆地干旱化趋势被高估超过 100%；垂直剖面图仅能由多层数据绘制，Python 中以 MetPy 的 cross_section 函数与 xarray 切片为两条实现路径，需注意气压坐标反转与对数化处理。工具选型上，Python 生态（xarray、MetPy、Cartopy、Matplotlib）以灵活定制见长，ECMWF 官方 Metview 工作站适合业务化批处理，NOAA WRIT 与 KNMI 在线工具适合快速探索。文末提供资料-图表速查对照表与常见实操问题解答。

## 1. ERA5 数据结构与变量体系：绘图前的数据认知

### 1.1 数据集总体结构与层次体系

ERA5 是欧洲中期天气预报中心（ECMWF）的第五代大气再分析产品，覆盖过去 80 年的全球气候与天气，数据可从 1940 年起获取[copernicus.eu](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels)。在产品组织上，ERA5 分为气压层数据与单层数据两大类，下载时需要将两者分别选择[ucar.edu](https://forum.mmm.ucar.edu/threads/how-to-use-era5-data-from-copernicus-database.19293/)。哥白尼气候数据存储（CDS）上，ERA5 共提供四个子集：逐小时产品与月平均产品，各自再分为气压层（高空场）与单层次（大气、海洋与陆面场）[copernicus.eu](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels)。这种层次组织方式直接决定了可绘制的图表类型：单层次数据只有一个垂直层，描述的是地表与近地面的二维状态，天然适合平面地图与时间序列；气压层数据包含多个标准等压面，构成三维场，既可以取其中一层绘制空间分布图，也可以沿垂直方向切开绘制剖面图。可以说，拿到一份 ERA5 资料后，判断它是单层还是多层，是选图的第一步。

从参数规格看，ERA5 相对其前身 ERA-Interim 有全面提升：ERA5 水平分辨率约 0.25°（约 31 km），时间分辨率为逐小时，垂直方向为 137 个模式层（顶层位于 0.01 hPa）；ERA-Interim 的水平分辨率约 0.75°（约 80 km），时间分辨率为 6 小时，垂直方向为 60 层（顶层位于 0.1 hPa）。常用的 ERA5 常规变量产品采用 0.25°×0.25° 网格、逐小时时间分辨率，格式为 NetCDF（.nc），按每天 1 个文件（24 个时次）存放。其气压层数据有 23 个常用层次，自高到低为 5、10、50、100、150、200、250、300、350、400、450、500、550、600、650、700、750、800、850、900、925、950、1000 hPa；CDS 另提供 37 层版本，高层包含 1、2、3、5、7、10、20 hPa，低层包含 875、900、925、950、975、1000 hPa。此外，ERA5-Land 以 0.1°×0.1°（约 10 km）的高分辨率提供陆面变量，时间跨度自 1950 年起，提供逐小时、逐日、逐月三种时间分辨率的产品。

**表1：ERA5 各数据流的结构参数对比**

| 数据流 | 垂直结构 | 水平分辨率 | 时间分辨率 | 时间覆盖 |
|--------|----------|------------|------------|----------|
| 单层次（Single Levels） | 1 层（地表与近地面）[ucar.edu](https://forum.mmm.ucar.edu/threads/how-to-use-era5-data-from-copernicus-database.19293/) | 0.25°（约 31 km） | 逐小时[copernicus.eu](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels) | 1940 年至今[copernicus.eu](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels) |
| 气压层（Pressure Levels） | 23 个常用层次（5–1000 hPa），另有 37 层版本 | 0.25° | 逐小时 | 1940 年至今 |
| 模式层（Model Levels） | 137 层，顶层 0.01 hPa | 0.25°（约 31 km） | 逐小时 | 与 ERA5 主产品一致 |
| ERA5-Land | 陆面单层（含 4 层土壤变量） | 0.1°×0.1°（约 10 km） | 逐小时、逐日、逐月 | 1950 年至今 |

从数据角色理解，单层次数据的作用有三项：一是提供下边界条件，如海表温度、雪深直接决定地表与大气之间的能量和水分交换；二是辅助三维场构建，例如地表气压是垂直坐标转换和近地面层变量诊断的关键输入；三是提供校验参考，模拟得到的 2m 气温、10m 风场可以直接与单层数据对比。气压层数据则定义了标准等压面上的温度、风、湿度、位势高度三维场，是构建大气三维结构的主体素材。一个常见误解是：有了高分辨率气压层数据，近地面单层数据就不重要了。实际上再分析资料在近地面（尤其是复杂地形区域）存在较大不确定性，两类数据需要配合使用，绘图选材时同样如此。

### 1.2 常用变量清单及其绘图属性

ECMWF 官方个例研究（Desmond 案例）的可视化体系中，单层次参数选取了 4 个代表性变量：2m 气温、平均海平面气压、降水、10m 阵风[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662)。在此基础上，ERA5 单层次常用变量还包括：2m 露点温度、地表气压、10m 纬向/经向风分量（u10/v10）、100m 纬向/经向风分量、海表温度、雪深、边界层高度、地表净热辐射、大气顶入射太阳辐射、总云量、低云量、中云量、高云量、对流有效位能（CAPE）、对流抑制（CIN）、表皮温度、4 层土壤温度与 4 层土壤体积含水量、总柱水汽、总柱液态水、零度层高度、K 指数、总指数。

**表2：ERA5 单层次常用变量及适配图表**

| 变量 | 物理意义 | 适配图表类型 |
|------|----------|--------------|
| 2m 气温 | 近地面空气温度 | 空间分布图、时间序列图[Read the Docs](https://earthkit-plots.readthedocs.io/en/latest/examples/examples/time-series/timeseries-introduction.html) |
| 平均海平面气压（MSLP） | 海平面气压 | 空间分布图（天气图）、时间序列图[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662) |
| 总降水量 | 累计降水 | 空间分布图、时间序列图[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662) |
| 10m U/V 风分量 | 近地面风场 | 空间分布图（填色、矢量）、时间序列图[CSDN](https://blog.csdn.net/weixin_45863084/article/details/147652722) |
| 10m 阵风 | 极大风速 | 空间分布图[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662) |
| 2m 露点温度 | 近地面湿度 | 空间分布图、时间序列图 |
| 地表气压 | 地面气压 | 空间分布图（辅助垂直坐标转换） |
| 海表温度 | 海洋表面温度 | 空间分布图、时间序列图 |
| 雪深 | 积雪深度 | 空间分布图、时间序列图 |
| 边界层高度 | 边界层厚度 | 空间分布图、时间序列图 |
| 土壤温度、土壤水分（各 4 层） | 陆面变量 | 时间序列图（多层对比折线）、空间分布图 |
| 总云量 | 云覆盖比例 | 空间分布图 |
| CAPE、对流抑制 | 对流稳定性指标 | 空间分布图、时间序列图 |

气压层变量方面，官方案例选取的代表性参数为：850 hPa 温度、500 hPa 位势、250 与 100 hPa 风、700 hPa 相对湿度[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662)。完整的气压层常用变量还包括：比湿、垂直速度、散度、涡度、位涡、臭氧质量混合比、云覆盖比例。

**表3：ERA5 气压层常用变量及适配图表**

| 变量（GRIB 短名） | 物理意义 | 常用层次 | 适配图表类型 |
|-------------------|----------|----------|--------------|
| 位势（z） | 位势高度场 | 500 hPa[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662) | 空间分布图（等值线）、垂直剖面图 |
| 温度（t） | 气温 | 850 hPa[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662) | 空间分布图、垂直剖面图、时间序列图 |
| U 风、V 风（u/v） | 水平风分量 | 250、100 hPa[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662) | 空间分布图（矢量、风羽）、垂直剖面图 |
| 相对湿度（r） | 湿度 | 700 hPa[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662) | 空间分布图、垂直剖面图 |
| 比湿（q） | 水汽含量 | 各气压层 | 垂直剖面图（水汽输送计算） |
| 垂直速度（w） | 垂直运动 | 各气压层 | 垂直剖面图 |
| 散度（d） | 辐合辐散 | 各气压层 | 垂直剖面图（纬圈平均剖面）[CSDN](https://blog.csdn.net/weixin_46921265/article/details/139374563) |
| 涡度 | 旋转性动力场 | 各气压层 | 空间分布图、垂直剖面图 |
| 位涡 | 保守性动力场 | 各气压层 | 空间分布图 |
| 臭氧质量混合比 | 臭氧含量 | 各气压层 | 垂直剖面图 |

在绘图之前，还需要掌握几项数据层面的前置知识。第一，ERA5 的风场以 U/V 分量形式存储：U 表示东西向风速（向东为正），V 表示南北向风速（向北为正）；换算公式为风速 speed = √(u²+v²)，风向 direction = (270 − arctan2(v,u) 角度值) mod 360，气象学风向定义为风的来向，正北为 0°，顺时针增加[CSDN](https://blog.csdn.net/weixin_29091837/article/details/159181949)。第二，温度变量单位为开尔文（K），绘制摄氏度需减去 273.15。第三，位势变量单位为 m²/s²，除以 9.81 或使用 MetPy 的 geopotential_to_height 函数可换算为几何高度，也可用静力学方程（取该层以下气层平均温度）换算；若需要从模式层插值到高度层，可使用 CDO 工具的 ml2hl 算子。

## 2. 空间分布图：什么资料画地图、怎么画

### 2.1 适用资料与典型场景

空间分布图适用于任一固定时刻（或时段平均后）的二维场：单层次变量可以直接成图，气压层变量需要先选定一个气压层，把该层的三维场降为二维场再绘制。天气个例分析与气候态平均是两大具有代表性的应用场景。

场景一：高空天气图。500 hPa 位势高度场是气象学中用于分析和预测天气的重要参数，大约对应 5500 m 高度；其等值线图能揭示西风带波动、高空槽脊与高压脊线位置，其中 588 线（500 hPa 等压面上位势高度 5880 gpm 的等值线）在天气学中具有特殊意义，常用来标识副热带高压的范围[CSDN](https://so.csdn.net/so/search/s.do?f=&from_code=app_blog_art&from_tracking_code=tag_word&l=&o=vip&q=python%E7%94%BB%E4%BD%8D%E5%8A%BF%E9%AB%98%E5%BA%A6%E5%9B%BE&s=&t=all&viparticle=)。夏季平均（6 月、7 月、8 月）的 500 hPa 位势高度场是气候分析的具有代表性的产品，绘制时通常将 588 线加深突出[CSDN](https://blog.csdn.net/weixin_31423955/article/details/161963804)。区域天气分析图中，则常把 500 hPa 高度等值线与温度等值线叠加，位势高度以位势十米（dagpm）为单位标注，并对高度场做高斯滤波平滑处理。

场景二：地面要素图。全球尺度的 10m 风速产品由 ERA5 的 u10、v10 风分量合成，叠加全球国界线 Shapefile，覆盖经度 −180° 至 180°、纬度 −90° 至 90° 范围[CSDN](https://blog.csdn.net/weixin_45863084/article/details/147652722)。在 2015 年 12 月风暴 Desmond 案例研究中，ECMWF 官方用 ERA5 绘制了 24 小时降水量（叠加海平面气压青色等值线）、2m 气温、10m 阵风、850 hPa 温度、700 hPa 相对湿度、500 hPa 位势、250 与 100 hPa 风场[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662)。这一组变量组合基本覆盖了强降水个例分析所需的地面与高空要素。

场景三：气候趋势与距平分布图。基于 ERA5-Land 可以绘制陆地水储量（TWS）、降水、径流、P−ET（降水减蒸散）年趋势的空间分布，并用打点方式标注趋势信度超过 95% 的格点（胡焕庸过渡带干旱化研究即采用此形式）。季节对比时，还可以绘制 7 月减 1 月的差异热力图，快速定位季节变化幅度最大的区域。

**表4：ERA5 空间分布图代表性案例**

| 案例 | 变量与层次 | 图形要素组合 | 说明 |
|------|------------|--------------|------|
| 500 hPa 位势高度场 | 位势，500 hPa[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662) | 等值线图（588 线加粗）[CSDN](https://so.csdn.net/so/search/s.do?f=&from_code=app_blog_art&from_tracking_code=tag_word&l=&o=vip&q=python%E7%94%BB%E4%BD%8D%E5%8A%BF%E9%AB%98%E5%BA%A6%E5%9B%BE&s=&t=all&viparticle=) | 分析西风槽脊与副热带高压[CSDN](https://so.csdn.net/so/search/s.do?f=&from_code=app_blog_art&from_tracking_code=tag_word&l=&o=vip&q=python%E7%94%BB%E4%BD%8D%E5%8A%BF%E9%AB%98%E5%BA%A6%E5%9B%BE&s=&t=all&viparticle=) |
| 夏季平均高度场 | 位势，500 hPa，6–8 月月平均[CSDN](https://blog.csdn.net/weixin_31423955/article/details/161963804) | 等值线图 | 气候态分析产品[CSDN](https://blog.csdn.net/weixin_31423955/article/details/161963804) |
| 全球 10m 风速 | u10、v10 合成风速[CSDN](https://blog.csdn.net/weixin_45863084/article/details/147652722) | 填色图叠加国界线[CSDN](https://blog.csdn.net/weixin_45863084/article/details/147652722) | 全球范围 −180° 至 180°、−90° 至 90°[CSDN](https://blog.csdn.net/weixin_45863084/article/details/147652722) |
| 风暴个例地面分析 | 24 小时降水、海平面气压、2m 气温、10m 阵风[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662) | 填色图叠加油压等值线 | Desmond 风暴案例[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662) |
| 风暴个例高空分析 | 850 hPa 温度、700 hPa 相对湿度、500 hPa 位势、250/100 hPa 风[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662) | 单层场填色或等值线 | Metview 宏批量绘制[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662) |
| 陆面要素趋势分布 | ERA5-Land 的 TWS、降水、径流、P−ET | 趋势填色图叠加显著性打点 | 胡焕庸过渡带研究 |

### 2.2 绘制要素组合与实现要点

填色图、等值线图、风矢量（含风羽、流线）是空间分布图的三类基本图形要素。全球 10m 风速产品使用 plt.contourf 绘制填色，配合自定义 ListedColormap 色表与 BoundaryNorm 归一化实现风级分档着色，数据通过 xarray 的 cfgrib 引擎读取 GRIB 文件，再用 geopandas 叠加国界线 Shapefile，输出 dpi 设为 600[CSDN](https://blog.csdn.net/weixin_45863084/article/details/147652722)。500 hPa 高度场则以 contour 绘制等值线，并对 588 线单独加深[CSDN](https://so.csdn.net/so/search/s.do?f=&from_code=app_blog_art&from_tracking_code=tag_word&l=&o=vip&q=python%E7%94%BB%E4%BD%8D%E5%8A%BF%E9%AB%98%E5%BA%A6%E5%9B%BE&s=&t=all&viparticle=)。业务综合分析图中，常见形态是填色图（或等值线图）上叠加风矢量或风羽；例如亚欧天气图在兰勃特投影上叠加 500 hPa 高度等值线与温度等值线，并标注数据源为 ECMWF Reanalysis v5（ERA5）。

投影选择直接影响成图效果。用 Cartopy 绘图时，Robinson 投影最适合展示全球风场的整体特征，PlateCarree（等距圆柱投影）做区域分析更准确，Orthographic（正射投影）适合汇报演示；区域天气图则常选用 LambertConformal（兰勃特保角投影），例如以 104°E 为中心经线绘制亚欧区域。绘图调用时，数据需传入 transform=ccrs.PlateCarree()，通过 ax.coastlines() 添加海岸线、gridlines 添加经纬网格，并用 set_extent 限定地图范围。

色阶处理有两条实用规则。其一，季节或时段对比时必须统一色标范围：取对比双方最小值作为 vmin、最大值作为 vmax，否则两幅图视觉不可比；差异场则使用 coolwarm 之类的发散色表并将 center 设为 0。其二，色阶设计应与物理意义对应：以风速为例，0–16 m/s 的日常风力范围用蓝色系，16 m/s 以上的危险大风用黄、橙、红警示色，让色阶与风级标准一一对应，既符合气象规范也兼顾色盲人群辨识。

## 3. 时间序列图：什么资料画时序、怎么画

### 3.1 适用资料与典型场景

时间序列图展示气象要素在单点或区域平均后的时间演变。对 ERA5 而言，任意变量的单点或区域平均时间演变都适合绘制时间序列图：单层次变量可以直接提取，气压层变量需要先固定层次，或先做垂直积分、垂直平均再提取。ClimateMatch 计算工具课程以 ERA5 再分析数据为素材，教授计算并比较不同变量的时间序列、用交互地图探索多个时间尺度上的变化[climatematch.io](https://comptools.climatematch.io/tutorials/W1D2_Ocean-AtmosphereReanalysis/student/W1D2_Tutorial2.html)；单站点的 ERA5 逐小时 2m 气温时间序列，则是 ECMWF 官方绘图库 earthkit-plots 文档的入门示例，数据从 CDS 获取[Read the Docs](https://earthkit-plots.readthedocs.io/en/latest/examples/examples/time-series/timeseries-introduction.html)。

具有代表性的应用场景有四类。第一类是单点逐小时或逐日曲线，例如 2m 气温、降水、10m 风速的演变，适合天气过程监测与个例复盘。第二类是多层或多深度对比折线图：例如基于 GEE 平台的 ERA5 土壤数据集，把 1951–2023 年 4 层土壤水分（0–7 cm、7–28 cm、28–100 cm、100–289 cm）年度均值绘制为折线图，用蓝、绿、橙、红四色区分深度，横轴为年份、纵轴为土壤水分（m³/m³）。第三类是区域平均距平曲线，例如全球陆地年平均降水、蒸发及 P−E 差值的逐年时间序列，用于气候监测。第四类是时间-高度综合廓线图：这是时间序列与垂直剖面的复合形态，本质是单站时间-高度二维数据的等值线或填色图，横轴为时间（业务上习惯从右向左读取）、纵轴为气压层，用于展示单站温度、湿度、风、垂直速度随时间的垂直演变，例如 2023 年 2 月 1 日至 4 日北京站（39.8°N、116.47°E）的 3 小时间隔综合廓线图。

如果不想本地编程，NOAA 物理科学实验室的再分析对比工具 WRIT 可以直接生成用户选定的再分析时间序列、散点图、互相关函数，还能绘制月平均地图、垂直剖面以及气候变量场与气候指数时间序列之间的季节相关图，投影可选圆柱等距、正射、墨卡托、摩尔威德、罗宾逊、兰勃特保角。KNMI 也提供时间序列绘图、年循环计算与滤波工具。

### 3.2 实现要点与趋势分析注意事项

实现层面有四个要点。第一，单点提取使用 xarray 的 sel 方法并指定 method='nearest'，取目标位置最近的格点[CSDN](https://blog.csdn.net/weixin_29091837/article/details/159181949)。第二，时间聚合使用 resample，但聚合方式会改变结果：对比"先算每日最大值再取月平均"与"直接取月平均"两种方法，实测发现北大西洋区域直接平均会低估约 1.5 m/s，这对风电发电量评估场景的影响是决定性的。第三，时间坐标转换：把 UTC 转为北京时，可先用 pd.to_datetime 设置 utc=True，再用 tz_convert('Asia/Shanghai') 转换时区，最后用 strftime('%d%H') 格式化为"日+时"显示。第四，绘制时间-高度廓线图时，需要用 transpose 调换（time，level）维度顺序，并对数组做反转，以满足"高度从低到高、时间从右到左"的业务读取习惯。

用于长期趋势分析时，必须警惕观测系统变迁引入的非均一性。北京大学王开存团队的研究揭示：ERA5 陆地降水存在虚假的下降趋势，由于 ERA5 降水被广泛用于驱动陆面模型，这一误差会传导至下游产品——基于 ERA5-Land 估计的 1980–2023 年陆地干旱化趋势，相较卫星观测约束结果被高估超过 100%，该问题在半干旱地区尤为隐蔽，容易与真实的气候变化信号混淆。研究团队同时强调，这并非否定 ERA5 的科学价值：ERA5 在 21 世纪仍是最可靠的再分析资料之一，广泛适用于天气和气候研究；但当其用于跨越观测系统发生重大变化的长期趋势分析时，非均一性必须被明确考虑。因此，时间序列图用于天气过程分析、年际变率研究、短期气候监测时结论稳健；用于数十年尺度的趋势研究时，需配套数据均一性讨论或与独立观测资料交叉验证。

## 4. 垂直剖面图：什么资料画剖面、怎么画

### 4.1 适用资料与典型场景

垂直剖面图只能由气压层或模式层三维数据绘制：剖面图展示的是气象要素沿某一方向（经度方向、纬度方向或任意路径）在垂直方向上的分布，单层次数据只有一个垂直层，无法构成剖面，这是剖面图选资料时的硬约束。剖面图用于揭示大气垂直结构，是诊断对流系统、锋面结构、急流与垂直运动的决定性图类。CDS 上 ERA5 气压层数据的垂直维度从地表覆盖到高空的多个标准等压面（如 1000 hPa 至 50 hPa）[CSDN](https://blog.csdn.net/weixin_29091837/article/details/159181949)。

常用的剖面变量可按诊断目的分为三组。第一组是热力与湿度变量：温度剖面揭示冷暖平流与层结稳定度，相对湿度或比湿剖面揭示水汽的垂直分布，北极海雾研究中，风向、风速、水汽压、海表温度的连续时间序列能够捕捉海雾的动态演变特征，海雾的发生与近海面温度的垂直梯度密切相关。第二组是动力变量：U/V 风剖面展示急流位置与风向随高度的旋转（风切变），垂直速度剖面展示上升下沉运动，散度剖面展示辐合辐散的垂直配置——一篇教程即使用 ERA5 散度数据绘制了沿纬圈平均的散度垂直剖面，纵轴取对数气压坐标，展示 200–1000 hPa 层次的纬向平均散度分布[CSDN](https://blog.csdn.net/weixin_46921265/article/details/139374563)。第三组是诊断量：水汽通量散度剖面用于诊断水汽的辐合辐散，计算时先由比湿 q 与风分量 u、v 得到水汽通量（q·u/g、q·v/g），再逐层用 mpcalc.divergence 求散度并拼接为三维场，最后用 MetPy 的 cross_section 提取剖面。

剖面场景按提取方式分为三类。第一类是沿固定经度或纬度的纬向/经向剖面，例如沿某条纬线做纬圈平均散度剖面[CSDN](https://blog.csdn.net/weixin_46921265/article/details/139374563)。第二类是沿任意路径的剖面，例如从（45°N，100°E）到（20°N，130°E）的风矢量剖面，用 MetPy 提取后可叠加地形与路径小地图。第三类是时间-高度剖面（综合廓线图），前文 3.1 节已述，此处不再展开。

**表5：ERA5 垂直剖面图常用变量及诊断意义**

| 变量 | 常用层次 | 诊断意义 | 剖面类型 |
|------|----------|----------|----------|
| 温度 | 各气压层[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662) | 冷暖平流、层结稳定度 | 固定经纬度或任意路径 |
| 比湿、相对湿度 | 各气压层[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662) | 水汽垂直分布、云与雾诊断 | 固定经纬度或任意路径 |
| U/V 风分量 | 各气压层[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662) | 急流、风切变、风向随高度旋转 | 任意路径剖面 |
| 垂直速度 | 各气压层 | 上升下沉运动强度与位置 | 纬圈平均或任意路径 |
| 散度 | 各气压层 | 辐合辐散垂直配置[CSDN](https://blog.csdn.net/weixin_46921265/article/details/139374563) | 纬圈平均剖面[CSDN](https://blog.csdn.net/weixin_46921265/article/details/139374563) |
| 水汽通量散度 | 各气压层 | 水汽辐合辐散、暴雨诊断 | 任意路径剖面 |
| 位势 | 各气压层 | 槽脊结构与厚度场 | 任意路径剖面 |

### 4.2 剖面提取与坐标处理要点

Python 中有两条主流实现路径。第一条是 MetPy 的 cross_section 函数：先用 xarray 打开气压层数据，选取时刻后调用 ds.metpy.parse_cf() 转换为 MetPy 的 CF 标准格式，再调用 cross_section(ds, start_point, end_point) 提取剖面，其中起点与终点以（纬度，经度）元组给出；提取结果包含沿剖面的 z、t、r、q、u、v、w 变量，维度为（level，index）。对风场可进一步调用 mpcalc.cross_section_components 计算沿剖面的切向分量 t_wind 与法向分量 n_wind，调用 mpcalc.vertical_velocity 由模式坐标垂直速度 w 换算气压垂直速度。一个常见报错是 cross_section 无法识别坐标：原因是数据未经 parse_cf 解析、缺少正确的 x、y 维度坐标或 crs 投影坐标，解决方法是确认 parse_cf 已正确执行。第二条是 xarray 直接切片：沿固定纬度或经度用 sel 切片后对另一水平维度取平均，实现简单、无需投影元数据，适合纬圈/经圈平均剖面[CSDN](https://blog.csdn.net/weixin_46921265/article/details/139374563)。

垂直坐标处理有三个要点。第一，气压坐标数值随高度增加而减小，绘图时必须调用 invert_yaxis() 反转纵轴，使高度自下而上递增，符合气象惯例[CSDN](https://blog.csdn.net/weixin_29091837/article/details/159181949)。第二，对数气压坐标：以 np.log10(level) 作为纵轴数值，再把刻度标签改回 200、300、500、700、850、1000 hPa，可以让低层细节在图中充分展开[CSDN](https://blog.csdn.net/weixin_46921265/article/details/139374563)。第三，几何高度换算：ERA5 只提供位势（位势高度），需要时可将位势除以 9.81 并用 MetPy 的 geopotential_to_height 换算，或用静力学方程（以该层以下平均温度）估算几何高度；若必须将模式层数据转换到固定高度层，可用 CDO 的 ml2hl 算子，但其对低层大气的内插外延效果需谨慎使用。

绘图美化与规范方面，剖面图中常嵌入小地图显示剖面路径的地理位置，增强图的实用性；也可在剖面图角落嵌入极坐标风向玫瑰图（16 个方位分箱、极坐标柱状图、theta 零点设在正北）直观展示风向频率分布[CSDN](https://blog.csdn.net/weixin_29091837/article/details/159181949)。输出分辨率一般设为 dpi 600 并用 bbox_inches='tight' 裁剪边距[CSDN](https://blog.csdn.net/weixin_46921265/article/details/139374563)。

## 5. 绘图工具选型：Python 生态、Metview 与在线工具

### 5.1 主流工具链能力对比

Python 生态以灵活定制能力成为科研绘图的主流选择，Metview 以 ECMWF 官方业务化工作流见长，在线工具适合无编程环境的快速探索，三者按场景互补而非替代。

Python 生态中各库的分工是：xarray 负责带标签的多维数组读取与操作，支持延迟加载与 Dask 分块，用 chunks={'time': 10} 启用分块处理、以时间维度分块优先，多文件场景使用 open_mfdataset，向量化运算相比显式循环在执行时间、代码可读性与内存占用上全面占优[CSDN](https://blog.csdn.net/weixin_32377497/article/details/161372217)；MetPy 负责气象物理计算，提供带单位的量纲检查（错误的单位组合会触发 UnitError）、内置物理常数与气象函数[CSDN](https://blog.csdn.net/weixin_32377497/article/details/161372217)；Cartopy 负责地图投影与地理要素绘制，支持墨卡托、极射、兰勃特保角投影，与 Matplotlib 深度整合，适合出版级地图，缺点是安装复杂、文档不够友好；Matplotlib 是基础绘图系统，功能全面、出版级图形质量、文档丰富，缺点是 API 偏底层、复杂图表代码量大；geopandas 负责矢量数据（国界、省界 Shapefile）叠加；此外 Plotly 与 Bokeh 适合交互式图表与 Web 展示，Mayavi、VisPy 适合三维体渲染。

Metview 是 ECMWF 的工作站软件，运行平台覆盖 UNIX（含 Mac OS X），从笔记本电脑到超级计算机均可使用，基于 MARS、ecCodes、Magics、ODB 构建，处理 GRIB、BUFR、NetCDF、ODB、Geopoints、CSV、ASCII 格式，以 Apache 2.0 协议开源；其界面采用图标式交互（数据、设置、过程以图标表示并可串联），并提供强大的 Macro 与 Python 接口支持批处理[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662)。Metview 5 自 2017 年发布后，新增了 Python 接口、改进的绘图层管理、100 余项参数的等值线编辑器与 300 余个预定义调色板、可复现 ecCharts 图层、BUFR 接口、FLEXPART 粒子扩散模型集成与 Met.3D 三维可视化接口。ECMWF 的 Desmond 案例研究即以 Metview 宏（plot_forecastrun.mv、plot_ERAI_ERA5.mv）完成 ERA5 参考场与预报场的批量可视化，支持交互式对话框与批处理两种模式。

在线工具方面，NOAA 的 WRIT 可在线绘制再分析时间序列、散点图、互相关函数、月平均地图、垂直剖面与季节相关图；KNMI 提供时间序列绘图、年循环计算与滤波工具；CDS 自带的 ERA explorer 应用提供全球气候数据的可视化访问。

**表6：ERA5 绘图工具能力对比**

| 工具 | 功能定位 | 优势 | 局限 |
|------|----------|------|------|
| xarray | 多维数据读取与操作 | 带标签维度、延迟加载、向量化运算[CSDN](https://blog.csdn.net/weixin_32377497/article/details/161372217) | 无投影与气象计算能力 |
| MetPy | 气象物理计算与剖面 | 量纲检查、内置气象函数、cross_section[CSDN](https://blog.csdn.net/weixin_32377497/article/details/161372217) | 需配合绘图库成图 |
| Cartopy | 地图投影与地理绘制 | 专业投影、出版级地图 | 安装复杂、文档不友好 |
| Matplotlib | 基础绘图 | 功能全面、出版质量、社区生态好 | API 底层、复杂图代码量大 |
| Metview | ECMWF 官方可视化工作站 | 图标交互、批处理宏、官方风格[ecmwf.int](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662) | 依赖 UNIX 环境、定制自由度低于代码 |
| WRIT / KNMI | 在线再分析绘图 | 免安装、免编程、快速探索 | 定制化程度有限 |

选择建议：初学者与快速出图需求可从在线工具入手，再过渡到 Python；科研论文图件推荐 xarray+MetPy+Cartopy+Matplotlib 组合，兼顾计算正确性与成图定制能力；ECMWF 体系内的业务预报检验与 ecCharts 风格图件推荐 Metview。

### 5.2 数据获取与绘图工作流

完整的 ERA5 绘图工作流分为六步。第一步，数据获取：在 CDS 注册账号后获取 API 密钥，通过 Python 脚本（cdsapi）按变量、层次、时间、区域提交请求下载，首次下载前需接受数据集许可协议；也可以直接在 CDS 网页界面上勾选变量后复制 API 请求代码。第二步，格式选择：NetCDF 格式用 xarray 直接读取；GRIB 格式用 cfgrib 引擎读取（ds = xr.open_dataset(path, engine='cfgrib')）[CSDN](https://blog.csdn.net/weixin_45863084/article/details/147652722)。第三步，按需裁剪：ERA5 全球常规变量数据总量超过 200 TB，务必在下载时限定变量、层次、时间与区域，避免下载整库；处理阶段用 sel 选取时间、层次与区域，用 chunks 分块加载避免内存溢出[CSDN](https://blog.csdn.net/weixin_32377497/article/details/161372217)。第四步，派生计算：包括 U/V 合成风速风向[CSDN](https://blog.csdn.net/weixin_29091837/article/details/159181949)、开尔文转摄氏度、位势换算高度、散度涡度与水汽通量散度诊断量计算。第五步，绘图输出：按第 2–4 章所述选择图类、投影与色阶。第六步，质检与归档：检查色标统一、坐标方向（气压轴反转）、图例单位与数据来源标注（建议标注"ECMWF Reanalysis v5 (ERA5)"字样）。

## 6. 快速对照与常见问题

把前三章的匹配关系收口为一张速查表，便于按需求即查即用。

**表7：ERA5 资料类型与图表类型速查对照**

| 图表类型 | 适配资料 | 必备数据处理 | 推荐工具 |
|----------|----------|--------------|----------|
| 空间分布图（填色、等值线、矢量） | 单层次任意变量；气压层变量取单层[ucar.edu](https://forum.mmm.ucar.edu/threads/how-to-use-era5-data-from-copernicus-database.19293/) | 选时选层、单位换算、风场合成[CSDN](https://blog.csdn.net/weixin_29091837/article/details/159181949) | xarray+Cartopy+Matplotlib |
| 时间序列图 | 任意变量的单点或区域平均[climatematch.io](https://comptools.climatematch.io/tutorials/W1D2_Ocean-AtmosphereReanalysis/student/W1D2_Tutorial2.html) | sel 选点、resample 聚合、时区转换[Read the Docs](https://earthkit-plots.readthedocs.io/en/latest/examples/examples/time-series/timeseries-introduction.html) | xarray+Matplotlib 或在线 WRIT |
| 时间-高度综合廓线图 | 气压层变量，单点提取 | 维度转置与反转、UTC 转北京时 | Matplotlib |
| 垂直剖面图 | 仅气压层或模式层变量 | cross_section 提取、气压轴反转[CSDN](https://blog.csdn.net/weixin_29091837/article/details/159181949) | MetPy+xarray+Matplotlib |

常见问题与解决要点如下。单位换算问题：温度为开尔文，绘图前减 273.15；风向由 U/V 按气象学来向定义换算，与数学极坐标存在 90° 偏差且方向相反[CSDN](https://blog.csdn.net/weixin_29091837/article/details/159181949)。维度顺序问题：不同来源的 NetCDF 文件维度顺序可能混乱，用 transpose 调整；读取后先断言 latitude、longitude、time 三个维度存在再处理。缺测问题：个别格点缺测可用插值处理；多来源数据混合时先统一单位（如 m/s 与度）。坐标问题：气压坐标绘图必须反转纵轴；MetPy cross_section 报错时先检查 parse_cf 是否执行成功[CSDN](https://blog.csdn.net/weixin_29091837/article/details/159181949)。色标问题：多时段或多数据集对比必须统一 vmin/vmax，差异场用中心为 0 的发散色表。趋势分析问题：ERA5 降水存在观测系统变迁引入的虚假下降趋势，基于 ERA5-Land 的干旱化趋势被高估超过 100%，数十年尺度趋势研究必须做均一性讨论或交叉验证。分辨率与代表性问题：0.25° 网格在复杂地形区域对近地面要素的表征存在不确定性，山区站点附近的小尺度特征不宜过度解读。

综上，ERA5 绘图的资料与图表匹配逻辑可以概括为：单层资料画平面（空间分布图与时序图），多层资料既画平面也画垂直（剖面图）；图表选择以科学问题为导向——看空间格局用分布图，看时间演变用序列图，看垂直结构用剖面图；工具选择以场景为导向——Python 生态保灵活、Metview 保业务规范、在线工具保快速。掌握数据结构、单位换算与坐标处理这三项基本功，即可覆盖绝大多数 ERA5 绘图需求。

## 核心参考文献

- [How to use ERA5 Data From Copernicus Database](https://forum.mmm.ucar.edu/threads/how-to-use-era5-data-from-copernicus-database.19293/)
- [Desmond case study](https://confluence.ecmwf.int/pages/viewpage.action?pageId=143047662)
- [Introduction to time series plots - earthkit-plots - Read the Docs](https://earthkit-plots.readthedocs.io/en/latest/examples/examples/time-series/timeseries-introduction.html)
- [python画位势高度图- CSDN搜索](https://so.csdn.net/so/search/s.do?f=&from_code=app_blog_art&from_tracking_code=tag_word&l=&o=vip&q=python%E7%94%BB%E4%BD%8D%E5%8A%BF%E9%AB%98%E5%BA%A6%E5%9B%BE&s=&t=all&viparticle=)
- [python绘制全球ERA5再分析数据10m风速产品_era5数据绘图-CSDN博客](https://blog.csdn.net/weixin_45863084/article/details/147652722)
- [ERA5 hourly data on single levels from 1940 to present](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels)
- [A Lot of Weather Makes Climate - Exploring the ERA5 ...](https://comptools.climatematch.io/tutorials/W1D2_Ocean-AtmosphereReanalysis/student/W1D2_Tutorial2.html)
- [【气象常用】剖面图_时间垂直剖面图 era5-CSDN博客](https://blog.csdn.net/weixin_46921265/article/details/139374563)
- [ERA5数据可视化指南：用Python绘制风速风向剖面图（含Matplotlib技巧）-CSDN博客](https://blog.csdn.net/weixin_29091837/article/details/159181949)
- [用Python+Cartopy绘制气象图：手把手教你画出专业的500hPa位势高度场与588线-CSDN博客](https://blog.csdn.net/weixin_31423955/article/details/161963804)
- [气象科研效率提升：用xarray和metpy优雅处理ERA5数据，自动计算Q1/Q2-CSDN博客](https://blog.csdn.net/weixin_32377497/article/details/161372217)
- [Cross Section Analysis — MetPy 1.7](https://unidata.github.io/MetPy/latest/examples/cross_section.html)
