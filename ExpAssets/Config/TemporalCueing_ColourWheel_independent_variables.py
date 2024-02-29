from klibs.KLStructure import FactorSet

exp_factors = FactorSet({
    "tone_onset": ["no_tone", "no_tone", "trial_start", "pre_target"],
    "foreperiod": [400, 1600],
    "warning": ["short", "long"],
    "warning_validity": ["valid" * 3, "invalid"],
    "target_duration": [33, 84]
})
