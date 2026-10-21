# Showcase page · 作品展示页

The page includes the Mandarin film from v0.1.0 and its English dub from v0.2.0. It includes native browser playback, character sheets, eight clickable shots and a super-resolution slider.

展示页提供 v0.1.0 的中文成片与 v0.2.0 的英文配音版，提供浏览器播放、人物定妆照、八个可跳转的分镜和超分对比滑块。

## Preview locally · 本地预览

~~~bash
gh release download v0.1.0 --repo Fengmc2001/ai-video-workflow --pattern traffic-safety-fengmc-1080p60.mp4 --dir .cache/site-media
gh release download v0.2.0 --repo Fengmc2001/ai-video-workflow --pattern traffic-safety-english-fengmc-1080p60.mp4 --dir .cache/site-media
python tools/build_showcase.py --video .cache/site-media/traffic-safety-fengmc-1080p60.mp4 --english-video .cache/site-media/traffic-safety-english-fengmc-1080p60.mp4
python tools/serve_showcase.py --directory dist/showcase
~~~

Open http://localhost:8766 in a browser. The builder checks the film's SHA256 against the case metadata. Choose an empty output directory when rebuilding, for example --output dist/showcase-next.

在浏览器打开 http://localhost:8766。构建脚本按案例中的 SHA256 核对视频；再次构建时，使用新的空输出目录，例如 --output dist/showcase-next。

## Publish · 发布

The Showcase workflow builds and deploys GitHub Pages when its source or media changes on main. It fetches the full film from the Release, keeping the large MP4 out of Git history.

main 上的页面或素材更新后，Showcase 工作流会构建并部署 GitHub Pages。完整 MP4 从 Release 取用，Git 历史中只保留页面与展示素材。

Frame times are in assets/showcase/shots.json. Comparison settings are in assets/showcase/comparison.json.

分镜取帧时间见 assets/showcase/shots.json，对比图参数见 assets/showcase/comparison.json。
