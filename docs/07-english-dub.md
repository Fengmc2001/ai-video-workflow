# The same story in English · 给故事配上英文

The English version keeps the finished animation and gives Lin Hao, Xu Nuo and Zhang Wei their own English dialogue. Both versions are 52.13 seconds, 1920×1080 at 60fps, with the Fengmc watermark.

英文版沿用成片画面，为林浩、许诺、张伟分别制作英文对白。中英文版均为52.13秒、1920×1080、60fps，保留Fengmc水印。

[Watch in English · 播放英文版](https://fengmc2001.github.io/ai-video-workflow/?lang=en#film) · [English script · 英文台词](../examples/traffic-safety/dialogue.en.json)

## Give each line a speaker · 每句都有说话人

The original characters' AI-generated voices serve as references. Each line is generated separately through Dreamina's seed_audio_v1 omni-dubbing mode, keeping the speaker and delivery attached to the dialogue.

使用原片中三个虚构角色的AI原声作为参考，通过即梦官方CLI的seed_audio_v1全能配音模式逐句生成。台词始终和角色、语气以及镜头对应。

An opening complaint, for example: “Cycling every day is exhausting!” Lin Hao says it casually; it leads into his wish for an e-bike.

例如开场的“Cycling every day is exhausting!”是一句随口的抱怨，自然接到林浩想换电动车的念头。

[Dreamina setup · 即梦准备](providers/dreamina.md) covers model discovery and quoting. Keep each generation's quote and task number in the working project.

模型发现和报价见[即梦准备](providers/dreamina.md)。每次生成前读取实时报价，在工作工程中保存对应任务编号。

## Finish the soundtrack · 把声音接回画面

Trim the silence around each generated line, keep complete word endings, then place the dialogue in its shot. Light tempo adjustments help it fit the scene. Demucs separates the original ambience for the new mix.

先去掉每句前后多余静音，保留完整尾字，再放到对应镜头。根据实际时长适度调整语速，用Demucs分离出的原片环境声完成混音。

Once the English WAV master is ready, copy the video stream into a new MP4:

英文WAV母版准备好后，复制原视频画面流，合成新的MP4：

~~~bash
ffmpeg -i film-mandarin.mp4 -i english-master.wav \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 256k \
  -ar 48000 -movie_timescale 48000 -movflags +faststart film-english.mp4
~~~

The exported English film is checked for full decoding, equal audio/video duration, frame timestamps and video-stream equality with the Mandarin version. Playback is available in both languages on the showcase page.

导出后检查完整解码、音视频等长、逐帧时间戳，并核对中英文版的画面码流一致。展示页可以直接切换两种配音观看。
