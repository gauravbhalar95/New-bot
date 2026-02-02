def main():
    # Your combined logic for the two main functions
    try:
        youtube_link = input('Enter YouTube link: ')
        if 'youtube.com/watch?v=' in youtube_link:
            video_id = youtube_link.split('v=')[1]
        elif 'youtu.be/' in youtube_link:
            video_id = youtube_link.split('/')[-1]
        else:
            raise ValueError('Invalid YouTube link')
        # Add remaining functionality here
        print(f'Video ID: {video_id}')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    main()