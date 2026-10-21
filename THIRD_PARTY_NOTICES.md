# 第三方组件

- RRDB 网络结构取自 [XPixelGroup/BasicSR](https://github.com/XPixelGroup/BasicSR)，Apache-2.0。代码位于 src/aivideo_workflow/_vendor/rrdb_arch.py，许可证在同目录 LICENSE-BasicSR.txt。
- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) 提供 x2plus 预训练权重。运行超分命令时从官方 Release 下载，仓库只保存下载地址和 SHA256。
- [FFmpeg](https://ffmpeg.org/) 用于本地音视频处理，通过命令行调用。
- 超分命令使用 [PyTorch](https://pytorch.org/)、[PyAV](https://pyav.basswood.io/) 和 [OpenCV](https://opencv.org/)。
\n- [Demucs](https://github.com/facebookresearch/demucs) is used locally to separate dialogue and ambience for the English dub. Demucs用于英文版的本地对白与环境声分离。\n