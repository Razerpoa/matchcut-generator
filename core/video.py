import os
import glob
import logging
import random
import numpy as np
from moviepy import ImageClip, ColorClip, concatenate_videoclips, AudioFileClip, concatenate_audioclips, CompositeVideoClip, AudioClip

from proglog import ProgressBarLogger

class MoviePyGuiLogger(ProgressBarLogger):
    def __init__(self, gui_callback):
        super().__init__()
        self.gui_callback = gui_callback

    def callback(self, **kw):
        # This handles general message updates from MoviePy
        if self.gui_callback and 'message' in kw:
            self.gui_callback(0, 0, kw['message'])

    def bars_callback(self, bar, attr, value, old_value=None):
        if self.gui_callback:
            if attr == 'index':
                total = self.bars.get(bar, {}).get('total', 1)
                self.gui_callback(value, total, f"Exporting {bar}: {value}/{total}")

class VideoGenerator:
    def __init__(self, output_dir="output"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def generate_default_audio(self, duration=0.1):
        """Generates a simple 'click' sound programmatically."""
        # Use a more stable way to create a short audio clip
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        audio_data = np.sin(2 * np.pi * 440 * t) * np.exp(-10 * t)
        
        # AudioData expects a (samples, channels) array
        from moviepy import AudioArrayClip
        return AudioArrayClip(audio_data.reshape(-1, 1), fps=sample_rate)

    def combine_crops_to_video(self, 
                               crops_dir="crops", 
                               output_name="matchcut_video.mp4", 
                               width=1080, 
                               height=1080, 
                               fps=24, 
                               frame_duration=2, 
                               use_audio=False, 
                               custom_audio_path=None,
                               shuffle=True,
                               progress_callback=None):
        
        image_files = sorted(glob.glob(os.path.join(crops_dir, "*.png")), key=os.path.getmtime)
        if shuffle:
            random.shuffle(image_files)
        if not image_files:
            logging.error("No crop images found in crops directory.")
            return None

        total_images = len(image_files)
        duration_per_clip = frame_duration / fps
        clips = []

        # Load transition audio if needed
        transition_audio = None
        if use_audio:
            # Check custom audio first
            if custom_audio_path and os.path.exists(custom_audio_path):
                try:
                    transition_audio = AudioFileClip(custom_audio_path)
                except Exception as e:
                    logging.warning(f"Could not load custom audio {custom_audio_path}: {e}")
            
            # Check assets folder for any audio file if no custom audio
            if transition_audio is None:
                assets_audio = glob.glob(os.path.join("assets", "audio", "*.*"))
                if assets_audio:
                    try:
                        transition_audio = AudioFileClip(assets_audio[0])
                        logging.info(f"Using default audio from assets: {assets_audio[0]}")
                    except Exception as e:
                        logging.warning(f"Could not load asset audio {assets_audio[0]}: {e}")

            # Fallback to generated audio
            if transition_audio is None:
                logging.info("Generating default 'click' audio.")
                transition_audio = self.generate_default_audio()
            
            # Trim or loop transition audio to fit the clip duration
            if transition_audio.duration > duration_per_clip:
                transition_audio = transition_audio.subclipped(0, duration_per_clip)
            else:
                # If it's shorter, we keep it as is (it will play at the start of the clip)
                pass

        for i, img_path in enumerate(image_files):
            if progress_callback:
                progress_callback(i, total_images, f"Processing clip {i+1}/{total_images}...")

            # Create black background
            bg = ColorClip(size=(width, height), color=(0, 0, 0), duration=duration_per_clip)
            
            # Load and scale image
            img_clip = ImageClip(img_path).with_duration(duration_per_clip)
            original_size = img_clip.size
            
            # Scale to fit width
            img_clip = img_clip.resized(width=width)
            
            # Ensure it fits height or scale down if it exceeds
            if img_clip.h > height:
                 img_clip = img_clip.resized(height=height)
            
            final_size = img_clip.size
            scale_factor = final_size[0] / original_size[0]

            # Realigned Centering Logic
            # Filename format: prefix_idx_CX_CY.png
            try:
                base_name = os.path.basename(img_path)
                parts = os.path.splitext(base_name)[0].split('_')
                # We expect at least prefix, idx, CX, CY (4 parts if prefix has no _)
                # But since prefix can have _, we work from the end
                cx_in_crop = int(parts[-2])
                cy_in_crop = int(parts[-1])
                
                # Scaled center coordinates
                scaled_cx = cx_in_crop * scale_factor
                scaled_cy = cy_in_crop * scale_factor
                
                # Align scaled_cx/cy to video center (width/2, height/2)
                # Position is (x, y) of top-left corner
                pos_x = (width / 2) - scaled_cx
                pos_y = (height / 2) - scaled_cy
                img_clip = img_clip.with_position((pos_x, pos_y))
                logging.debug(f"Realigned {base_name} to position ({pos_x}, {pos_y})")
            except (ValueError, IndexError):
                # Fallback to standard centering for old files or misformatted names
                img_clip = img_clip.with_position(('center', 'center'))
            
            # Compose clip
            final_clip = CompositeVideoClip([bg, img_clip])
            
            if use_audio and transition_audio:
                # Attach the transition audio to the clip
                # We need to make sure the audio duration matches the clip duration for concatenation
                clip_audio = transition_audio
                if transition_audio.duration < duration_per_clip:
                    # Pad with silence if audio is shorter than clip
                    from moviepy import AudioClip
                    silence = AudioClip(lambda t: 0, duration=duration_per_clip - transition_audio.duration).with_fps(44100)
                    clip_audio = concatenate_audioclips([transition_audio, silence])
                
                final_clip = final_clip.with_audio(clip_audio)
                
            clips.append(final_clip)

        if not clips:
            return None

        # Concatenate clips with audio attached
        final_video = concatenate_videoclips(clips, method="compose")

        output_path = os.path.join(self.output_dir, output_name)
        
        # Setup Logger
        logger = MoviePyGuiLogger(progress_callback) if progress_callback else 'bar'
            
        # Export
        final_video.write_videofile(output_path, fps=fps, codec='libx264', audio_codec='aac', logger=logger)
        
        return output_path
