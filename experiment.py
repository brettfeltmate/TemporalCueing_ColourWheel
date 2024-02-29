# -*- coding: utf-8 -*-

__author__ = "Brett Feltmate"

import klibs
from klibs import P
from klibs.KLUserInterface import any_key, ui_request, hide_cursor
from klibs.KLUtilities import deg_to_px, now
from klibs.KLText import add_text_style
from klibs.KLCommunication import message
from klibs.KLAudio import Tone
from klibs.KLGraphics import KLDraw as kld
from klibs.KLGraphics import fill, blit, flip, clear
from klibs.KLGraphics.colorspaces import COLORSPACE_CIELUV
from klibs.KLResponseListeners import ColorWheelListener

import numpy as np
import aggdraw as draw  # For drawing mask cells in a single texture
from PIL import Image
import random
import math

# Experiment constants #
# Colin: change these as desired

# Text constants
SHORTCUE = "SHORT"
LONGCUE = "LONG"

# Timing constants
WARN_TIME_MIN = 2000
WARN_TIME_MAX = 4000
TONE_ONSET_TARGET_ONSET = 50
TARGET_OFFSET_MASK_ONSET = 0
MASK_DURATION = 200
MASK_OFFSET_WHEEL_ONSET = 0
FEEDBACK_DURATION = 2000
RESPONSE_WINDOW = 50000  # set to None to disable timing out

# Audio constants
TONE_DURATION = 50
TONE_FREQ = 784 # Because you a G ridin' on your G5 airplane
TONE_VOLUME = 0.5
TONE_SHAPE = "sine"

# Size constants
FONT_SIZE_DEG = 1.0
BOX_SIZE_DEG = 2.0
FIX_STROKE_DEG = 0.2
WHEEL_RELATIVE_SIZE = 0.5

# Colour constants
FILL = (255, 255, 255, 255)  # White


class TemporalCueing_ColourWheel(klibs.Experiment):

    def setup(self):

        # Visual assets
        add_text_style("alert", size = deg_to_px(FONT_SIZE_DEG))

        self.box_size = deg_to_px(BOX_SIZE_DEG)

        self.fixation = kld.FixationCross(
            size=deg_to_px(BOX_SIZE_DEG), 
            thickness=deg_to_px(FIX_STROKE_DEG), 
            fill=FILL
        )

        self.target = kld.Rectangle(width = self.box_size)
        self.wheel = kld.ColorWheel(diameter = P.screen_y * WHEEL_RELATIVE_SIZE, colors=COLORSPACE_CIELUV)

        # Response collector
        self.wheel_listener = ColorWheelListener(self.wheel, timeout=RESPONSE_WINDOW)


        # Alerting tone
        self.tone = Tone(
            frequency=TONE_FREQ, 
            duration=TONE_DURATION, 
            volume=TONE_VOLUME, 
            wave_type=TONE_SHAPE
        )

        # Stitch in practice block when needed
        if P.practicing:
            # Currently set to 8 trials
            self.insert_practice_block(block_nums=1, trial_counts=P.trials_per_practice_block)

    def block(self):
        # Block & instructional text
        block_text = f"Block {P.block_number} of {P.blocks_per_experiment}"
        if P.practicing:
            block_text += "\n(practice block)"

        block_text += "\n\nAdd instuctions here"
        block_text += "\n\nPress any key to start block."

        fill()
        message(block_text, location=P.screen_c)
        flip()

        any_key()

    def trial_prep(self):

        # Randomly select target colour fill from COLORSPACE_CIELUV
        self.target_colour = COLORSPACE_CIELUV[random.randrange(0, len(COLORSPACE_CIELUV))]
        # Assign colour to target
        self.target.fill = self.target_colour
        # Inform listener of target colour
        self.wheel_listener.set_target(self.target_colour)


        # Generate mask
        self.mask = self.generate_mask()

        # trial timings
        if self.tone_onset == "trial_start":  
            self.evm.add_event("play_tone", 0)

        elif self.tone_onset == "pre_target":
            self.evm.add_event("play_tone",   self.foreperiod-TONE_ONSET_TARGET_ONSET)
        
        self.evm.add_event("target_on",       self.foreperiod)
        self.evm.add_event("target_off",      self.target_duration, after="target_on")
        self.evm.add_event("mask_on",         TARGET_OFFSET_MASK_ONSET, after="target_off")
        self.evm.add_event("mask_off",        MASK_DURATION, after="mask_on")
        self.evm.add_event("response_period", MASK_OFFSET_WHEEL_ONSET, after="mask_off")


        # Display appropriate temporal cue/warning/... I don't know what to call it
        fill()
        if self.warning == "short":
            warning = SHORTCUE if self.warning_validity == "valid" else LONGCUE
            message(warning, location=P.screen_c, style="alert")
        else:
            warning = LONGCUE if self.warning_validity == "valid" else SHORTCUE
            message(warning, location=P.screen_c, style="alert")
        flip()

        # Prevent early skipping
        allow_init_at = now() + (random.uniform(WARN_TIME_MIN, WARN_TIME_MAX) / 1000)
        while now() < allow_init_at:
            ui_request()

        # Any key to start trial
        any_key()

    def trial(self):
        hide_cursor()

        # Present fixation
        fill()
        blit(self.fixation, location=P.screen_c, registration=5)
        flip()

        # Play tone, if applicable
        if self.tone_onset != "no_tone":
            while self.evm.before("play_tone"):
                ui_request()

            self.tone.play()

        # Present target at appropriate time
        while self.evm.before("target_on"):
            ui_request()

        fill()
        blit(self.target, location=P.screen_c, registration=5)
        flip()

        # Clear target after appropriate time
        while self.evm.before("target_off"):
            ui_request()

        clear()
        
        # Present mask at appropriate time
        while self.evm.before("mask_on"):
            ui_request()

        fill()
        blit(self.mask, location=P.screen_c, registration=5)
        flip()

        # Clear mask after appropriate time
        while self.evm.before("mask_off"):
            ui_request()

        clear()

        # Collect response at appropriate time
        while self.evm.before("response_period"):
            ui_request()

        
        fill()
        blit(self.wheel, location=P.screen_c, registration=5)
        flip()

        angle_err, resp_color, rt = self.wheel_listener.collect()

        clear()

        if angle_err is None:
            angle_err, resp_color = "NA", "NA"
            fill()
            message("Response timeout!", location=P.screen_c, style="alert")
            flip()

        else:
            # Provide feedback
            self.feedback(angle_err, resp_color)

            feedback_end = now() + (FEEDBACK_DURATION / 1000)
            while now() < feedback_end:
                ui_request()

        clear()


        return {
            "block_num": P.block_number,
            "trial_num": P.trial_number,
            "practicing": P.practicing,
            "warning_type": self.warning,
            "warning_validity": self.warning_validity,
            "foreperiod": self.foreperiod,
            "tone_onset": self.tone_onset,
            "target_duration": self.target_duration,
            "target_colour": self.target_colour,
            "response_colour": resp_color,
            "response_angular_error": angle_err,
            "response_time": rt
        }

    def trial_clean_up(self):
        pass

    def clean_up(self):
        pass

    def feedback(self, angle_err, resp_color):
        # Convert angle error to percentage score
        score = (len(COLORSPACE_CIELUV) - abs(angle_err)) / len(COLORSPACE_CIELUV)
        score_msg = f"Accuracy: {score:.2%}"

        # Representations of actual and response colours
        actual = kld.Rectangle(width=deg_to_px(BOX_SIZE_DEG), fill=self.target_colour)
        response = kld.Rectangle(width=deg_to_px(BOX_SIZE_DEG), fill=resp_color)
        
        fill()

        blit(
            actual, 
            location = [P.screen_c[0]-deg_to_px(BOX_SIZE_DEG), 
                        P.screen_c[1]], 
            registration = 5
        )

        blit(
            response, 
            location = [P.screen_c[0]+deg_to_px(BOX_SIZE_DEG), 
                        P.screen_c[1]], 
            registration = 5
        )

        # Display feedback
        message(
            score_msg, 
            location = [P.screen_c[0], P.screen_c[1]-deg_to_px(2)], 
            style = "alert"
        )

        # Label colours
        message(
            "Actual", 
            location = [P.screen_c[0]-deg_to_px(BOX_SIZE_DEG) / 2, 
                        P.screen_c[1]+deg_to_px(BOX_SIZE_DEG)],
            registration = 6,
            style="alert"
        )

        message(
            "Response", 
            location = [P.screen_c[0]+deg_to_px(BOX_SIZE_DEG) / 2, 
                        P.screen_c[1]+deg_to_px(BOX_SIZE_DEG)],
            registration = 4,
            style="alert"
        )

        flip()



    def generate_mask(self):
        cells = 49
        # Set mask size
        canvas_size = deg_to_px(BOX_SIZE_DEG)
        # Set cell size
        cell_size = int(canvas_size / math.sqrt(cells))


        # Initialize canvas/surface (don't understand distinction)
        canvas = Image.new('RGBA', [canvas_size, canvas_size], (0, 0, 0, 0))
        surface = draw.Draw(canvas)

        # For outlines; genuinely can't remember if this is necessary
        cell_outline_width = deg_to_px(.001)
        transparent_pen = draw.Pen((0, 0, 0), cell_outline_width)

        count = int(math.sqrt(cells))

        # Generate cells, arranged in 4x4 array
        for row in range(count):
            for col in range(count):
                # Randomly select colour for each cell
                cell_colour = COLORSPACE_CIELUV[random.randrange(0, len(COLORSPACE_CIELUV))]
                # Brush to apply colour
                colour_brush = draw.Brush(tuple(cell_colour[:3]))
                # Determine cell boundary coords
                top_left = (row * cell_size, col * cell_size)
                bottom_right = ((row + 1) * cell_size, (col + 1) * cell_size)
                # Create cell
                surface.rectangle(
                    (top_left[0], top_left[1], bottom_right[0], bottom_right[1]),
                    transparent_pen,
                    colour_brush)
        # Apply cells to mask
        surface.flush()

        return np.asarray(canvas)