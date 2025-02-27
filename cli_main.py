import argparse
import asyncio
from datetime import datetime
from os.path import exists
from pathlib import Path

from conf import BASE_DIR
from uploader.douyin_uploader.main import douyin_setup, DouYinVideo
from uploader.ks_uploader.main import ks_setup, KSVideo
from uploader.tencent_uploader.main import weixin_setup, TencentVideo
from uploader.tk_uploader.main_chrome import tiktok_setup, TiktokVideo
from utils.base_social_media import get_supported_social_media, get_cli_action, SOCIAL_MEDIA_DOUYIN, \
    SOCIAL_MEDIA_TENCENT, SOCIAL_MEDIA_TIKTOK, SOCIAL_MEDIA_KUAISHOU
from utils.constant import TencentZoneTypes
from utils.files_times import get_title_and_hashtags


def parse_schedule(schedule_raw):
    if schedule_raw:
        schedule = datetime.strptime(schedule_raw, '%Y-%m-%d %H:%M')
    else:
        schedule = None
    return schedule


def get_video_files(path):
    """获取指定路径下的所有视频文件"""
    video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv'}
    path = Path(path)
    if path.is_file():
        return [str(path)] if path.suffix.lower() in video_extensions else []
    
    video_files = []
    for ext in video_extensions:
        video_files.extend([str(f) for f in path.glob(f'**/*{ext}')])
    return sorted(video_files)  # 按文件名排序


async def main():
    # 主解析器
    parser = argparse.ArgumentParser(description="Upload video to multiple social-media.")
    parser.add_argument("platform", metavar='platform', choices=get_supported_social_media(), 
                       help="Choose social-media platform: douyin tencent tiktok kuaishou")
    parser.add_argument("account_name", type=str, help="Account name for the platform: xiaoA")
    subparsers = parser.add_subparsers(dest="action", metavar='action', help="Choose action", required=True)

    actions = get_cli_action()
    for action in actions:
        action_parser = subparsers.add_parser(action, help=f'{action} operation')
        if action == 'login':
            continue
        elif action == 'upload':
            source_group = action_parser.add_mutually_exclusive_group(required=True)
            source_group.add_argument("-f", "--files", nargs='+', help="Path to one or more video files")
            source_group.add_argument("-d", "--directory", help="Path to directory containing videos")
            action_parser.add_argument("-pt", "--publish_type", type=int, choices=[0, 1],
                                     help="0 for immediate, 1 for scheduled", default=0)
            action_parser.add_argument('-t', '--schedule', help='Schedule UTC time in %Y-%m-%d %H:%M format')

    args = parser.parse_args()
    
    # 参数校验
    if args.action == 'upload':
        video_files = []
        if args.files:
            video_files = args.files
        elif args.directory:
            if not exists(args.directory):
                raise FileNotFoundError(f'Directory not found: {args.directory}')
            video_files = get_video_files(args.directory)
            if not video_files:
                raise ValueError(f'No video files found in directory: {args.directory}')
            print(f"找到 {len(video_files)} 个视频文件:")
            for video in video_files:
                print(f"- {video}")
            
        for video_file in video_files:
            if not exists(video_file):
                raise FileNotFoundError(f'Could not find the video file at {video_file}')
                
        if args.publish_type == 1 and not args.schedule:
            parser.error("The schedule must be specified for scheduled publishing.")

    account_file = Path(BASE_DIR / "cookies" / f"{args.platform}_{args.account_name}.json")
    account_file.parent.mkdir(exist_ok=True)

    # 根据 action 处理不同的逻辑
    if args.action == 'login':
        print(f"Logging in with account {args.account_name} on platform {args.platform}")
        if args.platform == SOCIAL_MEDIA_DOUYIN:
            await douyin_setup(str(account_file), handle=True)
        elif args.platform == SOCIAL_MEDIA_TIKTOK:
            await tiktok_setup(str(account_file), handle=True)
        elif args.platform == SOCIAL_MEDIA_TENCENT:
            await weixin_setup(str(account_file), handle=True)
        elif args.platform == SOCIAL_MEDIA_KUAISHOU:
            await ks_setup(str(account_file), handle=True)
    elif args.action == 'upload':
        video_files = args.files if args.files else get_video_files(args.directory)
        
        for video_file in video_files:
            title, tags = get_title_and_hashtags(video_file)

            if args.publish_type == 0:
                print(f"正在上传: {video_file}")
                publish_date = 0
            else:
                print(f"计划上传: {video_file}")
                publish_date = parse_schedule(args.schedule)

            if args.platform == SOCIAL_MEDIA_DOUYIN:
                await douyin_setup(account_file, handle=False)
                app = DouYinVideo(title, video_file, tags, publish_date, account_file)
            elif args.platform == SOCIAL_MEDIA_TIKTOK:
                await tiktok_setup(account_file, handle=True)
                app = TiktokVideo(title, video_file, tags, publish_date, account_file)
            elif args.platform == SOCIAL_MEDIA_TENCENT:
                await weixin_setup(account_file, handle=True)
                category = TencentZoneTypes.LIFESTYLE.value  # 标记原创需要否则不需要传
                app = TencentVideo(title, video_file, tags, publish_date, account_file, category)
            elif args.platform == SOCIAL_MEDIA_KUAISHOU:
                await ks_setup(account_file, handle=True)
                app = KSVideo(title, video_file, tags, publish_date, account_file)
            else:
                print("Wrong platform, please check your input")
                exit()

            await app.main()
            print(f"完成上传: {video_file}")


if __name__ == "__main__":
    asyncio.run(main())
