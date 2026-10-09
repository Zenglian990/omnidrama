"""OmniDrama 命令行启动入口 (CLI)."""
import argparse
import asyncio
import os
import sys

# 兼容 Windows 终端编码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from omnidrama.core.pipeline import OmniDramaPipeline


def main():
    parser = argparse.ArgumentParser(description="OmniDrama (灵眸漫剧) - 工业级 AI 漫剧导演系统")
    parser.add_argument("--story", type=str, help="输入故事文本文件路径或文本内容", required=True)
    parser.add_argument("--title", type=str, default="我的AI漫剧第一集", help="短剧标题")
    parser.add_argument("--genre", type=str, default="都市热血", help="题材风格 (如: 都市热血 / 悬疑惊悚 / 仙侠修真)")
    parser.add_argument("--outdir", type=str, default="omnidrama/output", help="输出根目录")
    parser.add_argument("--width", type=int, default=720, help="视频宽度 (默认720竖屏，可选1080)")
    parser.add_argument("--height", type=int, default=1280, help="视频高度 (默认1280竖屏，可选1920)")

    args = parser.parse_args()

    # 读取故事文本
    if os.path.exists(args.story):
        with open(args.story, "r", encoding="utf-8") as f:
            story_text = f.read()
    else:
        story_text = args.story

    print("=" * 60)
    print(f"[OmniDrama] 灵眸漫剧引擎启动...")
    print(f"[项目信息] 剧名: {args.title} | 题材: {args.genre}")
    print(f"[规格配置] 画布分辨率: {args.width}x{args.height}")
    print("=" * 60)

    pipeline = OmniDramaPipeline(
        output_dir=args.outdir,
        width=args.width,
        height=args.height
    )

    result = asyncio.run(pipeline.run_from_text(
        story_text=story_text,
        title=args.title,
        genre=args.genre
    ))

    print("\n" + "=" * 60)
    print("[成功] 漫剧成片生成完毕！")
    print(f"[成片视频] {result['final_video']}")
    print(f"[SRT 字幕] {result['subtitles_srt']}")
    print(f"[镜头清单] 共 {len(result['shots'])} 个分镜镜头已全部完成音视频对齐")
    print("=" * 60)


if __name__ == "__main__":
    main()
