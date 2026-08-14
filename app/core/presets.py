"""区域预设与常用数据集模板。"""

# 键为界面显示名，值为 CDS area 格式 [北, 西, 南, 东]
AREA_PRESETS = {
    "全球": None,
    "中国": [54, 73, 18, 135],
    "东北": [53, 118, 38, 135],
    "华北": [42, 110, 35, 119],
    "华东": [37, 114, 23, 123],
    "华中": [36, 108, 26, 116],
    "华南": [26, 105, 18, 118],
    "西南": [34, 80, 21, 110],
    "西北": [49, 73, 31, 111],
}

# 内置数据集模板；params 不含 data_format（由界面输出格式统一控制）
DATASET_TEMPLATES = {
    "ERA5 单层小时": {
        "dataset": "reanalysis-era5-single-levels",
        "params": {
            "product_type": "reanalysis",
            "variable": "2m_temperature",
        },
    },
    "ERA5 气压层": {
        "dataset": "reanalysis-era5-pressure-levels",
        "params": {
            "product_type": "reanalysis",
            "pressure_level": "1000",
            "variable": "temperature",
        },
    },
    "ERA5-Land 小时": {
        "dataset": "reanalysis-era5-land",
        "params": {
            "variable": "2m_temperature",
        },
    },
    "ERA5 单层月平均": {
        "dataset": "reanalysis-era5-single-levels-monthly-means",
        "params": {
            "product_type": "monthly_averaged_reanalysis",
            "variable": "2m_temperature",
        },
    },
}

# 数据集目录：界面显示名（与官网名称对应）→ CDS 数据集短名（API 参数）
DATASET_CATALOG = {
    "ERA5 小时·单层（1940-至今）": "reanalysis-era5-single-levels",
    "ERA5 小时·气压层（1940-至今）": "reanalysis-era5-pressure-levels",
    "ERA5-Land 小时（1950-至今）": "reanalysis-era5-land",
    "ERA5-Land 日统计（1950-至今）": "derived-era5-land-daily-statistics",
    "ERA5 单层月平均（1940-至今）": "reanalysis-era5-single-levels-monthly-means",
    "ERA5 气压层月平均（1940-至今）": "reanalysis-era5-pressure-levels-monthly-means",
    "ERA5-Land 月平均（1950-至今）": "reanalysis-era5-land-monthly-means",
}

# 常用气象要素：数据集短名 → 可选变量（下拉可编辑，支持手动输入）
DATASET_VARIABLES = {
    "reanalysis-era5-single-levels": [
        "2m_temperature",
        "2m_dewpoint_temperature",
        "surface_pressure",
        "mean_sea_level_pressure",
        "10m_u_component_of_wind",
        "10m_v_component_of_wind",
        "total_precipitation",
        "sea_surface_temperature",
        "skin_temperature",
        "surface_net_solar_radiation",
        "surface_net_thermal_radiation",
        "total_cloud_cover",
        "boundary_layer_height",
    ],
    "reanalysis-era5-pressure-levels": [
        "temperature",
        "geopotential",
        "u_component_of_wind",
        "v_component_of_wind",
        "vertical_velocity",
        "relative_humidity",
        "specific_humidity",
        "vorticity",
        "ozone_mass_mixing_ratio",
    ],
    "reanalysis-era5-land": [
        "2m_temperature",
        "2m_dewpoint_temperature",
        "total_precipitation",
        "surface_net_solar_radiation",
        "surface_net_thermal_radiation",
        "volumetric_soil_water_layer_1",
        "volumetric_soil_water_layer_2",
        "soil_temperature_level_1",
        "soil_temperature_level_2",
        "snow_depth_water_equivalent",
    ],
    # 日统计（derived）数据集省略累积变量（如总降水/径流，参见 CDS 官方文档），
    # 且使用 daily_statistic / frequency / time_zone 参数
    "derived-era5-land-daily-statistics": [
        "2m_temperature",
        "2m_dewpoint_temperature",
        "surface_net_solar_radiation",
        "volumetric_soil_water_layer_1",
        "soil_temperature_level_1",
    ],
    "reanalysis-era5-single-levels-monthly-means": [
        "2m_temperature",
        "2m_dewpoint_temperature",
        "surface_pressure",
        "mean_sea_level_pressure",
        "10m_u_component_of_wind",
        "10m_v_component_of_wind",
        "total_precipitation",
        "sea_surface_temperature",
        "surface_net_solar_radiation",
    ],
    "reanalysis-era5-pressure-levels-monthly-means": [
        "temperature",
        "geopotential",
        "u_component_of_wind",
        "v_component_of_wind",
        "specific_humidity",
    ],
    "reanalysis-era5-land-monthly-means": [
        "2m_temperature",
        "2m_dewpoint_temperature",
        "total_precipitation",
        "volumetric_soil_water_layer_1",
        "soil_temperature_level_1",
    ],
}
