# Dreamina：分段生成画面与同期声

《骑电动车的小争论》采用电影感三维动画，人物设定图、场景图和两段视频都在Dreamina完成。对白直接写进视频提示词，使用视频自带的普通话同期声。

先准备人物、场景和道具参考。生成G1后，截出林浩、许诺各自清楚完整的一句对白，作为G2的声音参考；再取G1末帧，接续三人的站位和自行车。

使用官方CLI时，先读取当前安装版本的命令与模型规格：

```bash
dreamina-canvas version
dreamina-canvas schema
dreamina-canvas auth status
dreamina-canvas model list --type video
```

确定模型、时长、画幅、分辨率和数量后，读取实时报价再提交。每段保存自己的任务编号，后续查询同一条任务。

也可以按导出的上传清单在网页操作。生成完成后，先检查台词、说话人、脸和动作，再使用内插工具选择60fps并下载。

入口：[Dreamina](https://dreamina.capcut.com/)。本地后期接[超分与合成](../06-postproduction.md)。
