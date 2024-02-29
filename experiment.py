# -*- coding: utf-8 -*-

__author__ = "Brett Feltmate"

import klibs

from klibs                        import P
from klibs.KLGraphics             import KLDraw as kld
from klibs.KLGraphics             import fill, blit, flip, clear
from klibs.KLGraphics.colorspaces import COLORSPACE_CIELUV
from klibs.KLResponseListeners    import ColorWheelListener
from klibs.KLUserInterface        import any_key, ui_request, hide_cursor
from klibs.KLUtilities            import deg_to_px, now
from klibs.KLText                 import add_text_style
from klibs.KLCommunication        import message
from klibs.KLAudio                import Tone

# For colour patch masks
from PIL     import Image
from aggdraw import Draw, Pen, Brush
from numpy   import asarray

import random
import math

# Experiment constants #
# change as desired

# Text constants
SHORTCUE = "SHORT"
LONGCUE  = "LONG"

# Timing constants (ms)
WARN_TIME_RANGE          = (2000, 4000)
TONE_ONSET_TARGET_ONSET  = 50
TONE_DURATION            = 50
TARGET_OFFSET_MASK_ONSET = 0
MASK_DURATION            = 200
MASK_OFFSET_WHEEL_ONSET  = 0
FEEDBACK_DURATION        = 2000
RESPONSE_WINDOW          = 50000  # None to disable timeout

# Audio constants
TONE_FREQ   = 784      # Ridin' on yo G5 airplane
TONE_VOLUME = 0.5
TONE_SHAPE  = "sine"

# Size constants
FONT_SIZE_DEG       = 1.0
BOX_SIZE_DEG        = 2.0
FIX_STROKE_DEG      = 0.2
WHEEL_RELATIVE_SIZE = 0.5

# Colour constants
FILL = (255, 255, 255, 255)  # White


class TemporalCueing_ColourWheel(klibs.Experiment):

    def setup(self):

        # Alerting tone
        self.tone = Tone(
            frequency = TONE_FREQ, 
            duration  = TONE_DURATION, 
            volume    = TONE_VOLUME, 
            wave_type = TONE_SHAPE
        )

        # Visual assets
        add_text_style("alert", size = deg_to_px(FONT_SIZE_DEG))

        self.box_size = deg_to_px(BOX_SIZE_DEG)

        self.fixation = kld.FixationCross(
            size      = deg_to_px(BOX_SIZE_DEG), 
            thickness = deg_to_px(FIX_STROKE_DEG), 
            fill      = FILL
        )

        self.target = kld.Rectangle(width = self.box_size)

        self.wheel = kld.ColorWheel(
            diameter = P.screen_y*WHEEL_RELATIVE_SIZE, 
            colors = COLORSPACE_CIELUV
        )   # const lum & sat


        # Response collector
        self.wheel_listener = ColorWheelListener(self.wheel, timeout = RESPONSE_WINDOW)


        if P.practicing:
            # Currently set to 8 trials
            self.insert_practice_block(block_nums = 1, trial_counts = P.trials_per_practice_block)


    def block(self):
        block_text = f"Block {P.block_number} of {P.blocks_per_experiment}"

        if P.practicing:
            block_text += "\n(practice block)"

        block_text += "\n\nAdd instuctions here"
        block_text += "\n\nAny key to start block."

        fill()
        message(block_text, location = P.screen_c)
        flip()

        any_key()


    def trial_prep(self):
        self.mask = self.generate_mask()

        # randomize wheel & target properties
        self.wheel.rotation = random.randrange(0, 360)
        self.wheel.render()                               
        
        self.target_colour  = self.wheel.color_from_angle(random.randrange(0, 360))  # (const lum)
        self.target.fill    = self.target_colour                                     
        
        self.wheel_listener.set_target(self.target_colour)                           


        # event timings, relative
        if self.tone_onset == "trial_start":  
            self.evm.add_event("play_tone",   0)

        elif self.tone_onset == "pre_target":
            self.evm.add_event("play_tone",   self.foreperiod-TONE_ONSET_TARGET_ONSET)
        
        self.evm.add_event("target_on",       self.foreperiod)
        self.evm.add_event("target_off",      self.target_duration,     after="target_on")
        self.evm.add_event("mask_on",         TARGET_OFFSET_MASK_ONSET, after="target_off")  # asynchrony currently 0ms
        self.evm.add_event("mask_off",        MASK_DURATION,            after="mask_on")
        self.evm.add_event("response_period", MASK_OFFSET_WHEEL_ONSET,  after="mask_off")


        # cue foreperiod
        fill()

        if self.warning == "short":
            message(
                SHORTCUE if self.warning_validity == "valid" else LONGCUE, 
                location = P.screen_c, 
                style    = "alert"
            )
        
        else:
            message(
                LONGCUE  if self.warning_validity == "valid" else SHORTCUE, 
                location = P.screen_c, 
                style    = "alert"
            )
        
        flip()

        # prevent early start
        allow_init_at = now() + (random.uniform(WARN_TIME_RANGE[0], WARN_TIME_RANGE[1]) / 1000)  # ms to s
        
        while now() < allow_init_at:
            ui_request()  

        # any key to start
        any_key()

    def trial(self):
        hide_cursor()

        # fixation period
        fill()
        blit(self.fixation, location = P.screen_c, registration = 5)
        flip()

        # alert signal (as needed)
        if self.tone_onset != "no_tone":

            while self.evm.before("play_tone"):
                ui_request()

            self.tone.play()

        # target-mask seq
        while self.evm.before("target_on"):
            ui_request()

        fill()
        blit(self.target, location=P.screen_c, registration=5)
        flip()

        while self.evm.before("target_off"):
            ui_request()


        if TARGET_OFFSET_MASK_ONSET > 0:
            clear()
            while self.evm.before("mask_on"):
                ui_request()


        fill()
        blit(self.mask, location=P.screen_c, registration=5)
        flip()


        while self.evm.before("mask_off"):
            ui_request()


        if MASK_OFFSET_WHEEL_ONSET > 0:
            clear()
            while self.evm.before("response_period"):
                ui_request()


        fill()
        blit(self.wheel, location=P.screen_c, registration=5)
        flip()


        # (auto-timeouts)
        angle_err, resp_color, rt = self.wheel_listener.collect()


        # Feedback on performance
        self.feedback(angle_err, resp_color)
        
        feedback_end = now() + (FEEDBACK_DURATION / 1000)   # ms to s
        while now() < feedback_end:
            ui_request()


        # Tidy up missing responses
        if angle_err is None:
            angle_err, resp_color = "NA", "NA"

        return {
            "block_num":              P.block_number,
            "trial_num":              P.trial_number,
            "practicing":             P.practicing,
            "warning_type":           self.warning,
            "warning_validity":       self.warning_validity,
            "foreperiod":             self.foreperiod,
            "tone_onset":             self.tone_onset,
            "target_duration":        self.target_duration,
            "target_colour":          self.target_colour,
            "response_colour":        resp_color,
            "response_angular_error": angle_err,
            "response_time":          rt
        }

    def trial_clean_up(self):
        clear()

    def clean_up(self):
        pass

    def feedback(self, angle_err: float = None, resp_color: tuple = None):
        fill()

        # admonish missing responses
        if angle_err is None:
            message("Response timeout!", location=P.screen_c, style="alert")

        else:

            # target & response tokens
            response = kld.Rectangle(width = deg_to_px(BOX_SIZE_DEG), fill = resp_color)
            actual   = kld.Rectangle(width = deg_to_px(BOX_SIZE_DEG), fill = self.target_colour)
            

            blit(
                actual, 
                location = [P.screen_c[0]-deg_to_px(BOX_SIZE_DEG),  # x,y
                            P.screen_c[1]], 
                registration = 5
            )

            blit(
                response, 
                location = [P.screen_c[0]+deg_to_px(BOX_SIZE_DEG), 
                            P.screen_c[1]], 
                registration = 5
            )

            # performance text
            acc = 1 - abs(angle_err) / 360

            message(
                text         = f"Accuracy: {acc*100:.0f}%",  # percentage
                style        = "alert",
                registration = 5,                            # center-justified
                location     = [P.screen_c[0], 
                                P.screen_c[1]-deg_to_px(2)]
            )

            # token labels
            message(
                text         = "Actual", 
                style        = "alert",
                registration = 6, # right-justified
                location     = [P.screen_c[0]-deg_to_px(BOX_SIZE_DEG) / 2, 
                                P.screen_c[1]+deg_to_px(BOX_SIZE_DEG)]
            )

            message(
                text         = "Response", 
                style        = "alert",
                registration = 4, # left-justified
                location     = [P.screen_c[0]+deg_to_px(BOX_SIZE_DEG) / 2, 
                                P.screen_c[1]+deg_to_px(BOX_SIZE_DEG)]
            )


        flip()



    def generate_mask(self):
        cells = 49
       
        # mask size
        canvas_size = deg_to_px(BOX_SIZE_DEG)
        # cell size
        cell_size = int(canvas_size / math.sqrt(cells))


        # transparent canvas
        canvas = Image.new('RGBA', [canvas_size, canvas_size], (0, 0, 0, 0))
        surface = Draw(canvas)

        # cell outlines
        cell_outline_width = deg_to_px(.001)
        transparent_pen = Pen((0, 0, 0), cell_outline_width)

        count = int(math.sqrt(cells))

        # cell array, randomly coloured
        for row in range(count):
            for col in range(count):

                cell_colour = COLORSPACE_CIELUV[random.randrange(0, len(COLORSPACE_CIELUV))]
                colour_brush = Brush(tuple(cell_colour[:3]))
                

                top_left = (row * cell_size, col * cell_size)
                bottom_right = ((row + 1) * cell_size, (col + 1) * cell_size)

                surface.rectangle(
                    (top_left[0], top_left[1], bottom_right[0], bottom_right[1]),
                    transparent_pen,
                    colour_brush)
                
        # apply 
        surface.flush()

        return asarray(canvas)