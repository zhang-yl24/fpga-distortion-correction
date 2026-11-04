# 鱼眼输出视场与边缘拉伸对比

2026-11-04离线实验。全部方案使用用户确认的11月3日凌晨同批原始图，固定现有KB4鱼眼标定K/D，只改变输出投影/视场。此实验与此前KB4-T2标定实验分开，避免把更换投影的收益归因于切向系数。没有更换为Brown模型。

## 结论与选择

原输出是水平视场约124.90°的直线透视图。大视场下，x=f*tan(角度)使边缘角度在像素平面被放大。这是输出投影的几何取舍；更精细的镜头标定并不能消除它。

- 当前比赛赶进度：优先试110°透视（仍1920×1080输出），保直线并减少两侧最极端区域，代价是视野裁切；105°更紧。现有mapper可通过输出K常量调整实现，但需要重新生成位流并验证定点映射、时序。源K/D和当前按r²定义的KB径向表不需要为了裁切而重新标定。
- 若更看重保留宽视野且边缘比例自然：Panini d=1在本例保留相同水平视场，压缩两侧拉伸，但一般横线会弯。竖直线和穿投影中心的直线有保直性质，不能宣称所有直线仍直。需要新增目标射线映射，不是只改k系数或现有径向表即可。
- 输入鱼眼模型、输出投影是两个独立选择；KB4/KB4-T2都可以搭配上述输出方案。

## 同口径几何数据

| 输出方式 | 水平视场 | 左/右边缘角度放大率（相对中心） | 落在源图内的输出像素比例 |
|---|---:|---:|---:|
| Current perspective | 124.90° | 4.22 / 5.21 | 89.73% |
| Perspective 110 deg | 110.00° | 3.04 / 3.04 | 99.48% |
| Perspective 105 deg | 105.00° | 2.70 / 2.70 | 100.00% |
| Panini d=1, same horizontal FOV | 124.90° | 1.35 / 1.39 | 100.00% |

角度放大率是中心水平截面上的局部导数dx/d(longitude)比值，不是物体普遍被放大的倍数、标定误差或帧率。源图内比例按960×540快照映射逐像素判断；有效像素变多同时伴随视场/投影变化，不能作为单独画质增益。相同水平视场不表示垂直视场也相同。

## 查看图片

每张对比图四格依次为：左上原鱼眼、右上当前约125°透视、左下110°透视、右下相同水平视场Panini。

- [右侧棋盘及书架，view 30](view-30-comparison.png)
- [左侧棋盘及桌面，view 20](view-20-comparison.png)
- [下边缘棋盘，view 0](view-00-comparison.png)
- [上边缘棋盘，view 5](view-05-comparison.png)
- [105°透视单图](view-30-perspective-105.png)

全部是PC离线重映射，并非上板效果。原图960×540，不能凭本图评价原生1080p细节分辨率。

## 复现与数学边界

透视输出逆映射射线为[xn,yn,1]；Panini d=1、无squeeze的射线为[xn,yn,1-xn²/4]，其中xn=(u-cx)/fx、yn=(v-cy)/fy。再用同一源KB4模型投影到原图，双线性采样。Panini的水平左右极限与当前输出精确匹配，其纵向视野随投影改变。两种裁切透视使用居中主点与相同fx/fy，当前及Panini保留说明中列出的主点。

原投影与OpenCV逐像素映射最大差0.0快照像素，全部方案映射有限，正深度成立。全部Kout（快照及原生等效）见result.json。输出常量在现有RTL中为编译常量；采样地址变化也可能改变DDR缓存命中，未测得任何新的FPGA帧率。

```powershell
.venv/Scripts/python.exe distortion/tools/compare_fisheye_projections.py --output distortion/work/fisheye-output-projections-NEW
```

依据：[Panini原论文](https://diglib.eg.org/items/29b67abe-d80e-4010-a065-e8292a8c65ef)、[Epic官方Panini投影说明](https://dev.epicgames.com/documentation/en-us/unreal-engine/panini-projection-in-unreal-engine)。
