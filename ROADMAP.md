# Roadmap

## Next Stabilization
- Continue splitting `blaster/main.py` into scene, wave, save, and UI modules.
- Replace global Pygame display/event hooks with explicit render and event adapter methods.
- Move or archive the unused `blaster_game.py` prototype so the active code path is unambiguous.
- Add manual smoke-test notes for release builds and fullscreen/window resize behavior.

## Gameplay
- Dash or dodge action with cooldown and clear visual feedback.
- More enemy patterns and elite variants.
- Better boss behavior phases with stronger telegraphs and arena pressure.
- Achievements and profile stats
- Sound/music volume split
- Save slot for control remapping

## Content And Release
- Real sprite pack and SFX pass
- Polished onboarding/tutorial wave
- Release pipeline with prebuilt Windows binary
- Code-signed Windows releases or Microsoft Store distribution to reduce SmartScreen/Defender blocks
- False-positive submission checklist for Microsoft Security Intelligence when Defender incorrectly flags a clean build
