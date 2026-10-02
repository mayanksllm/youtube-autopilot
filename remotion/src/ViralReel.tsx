import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Captions, CaptionBurst } from "./Captions";

export interface SceneData {
  imageSrc: string;
  durationInFrames: number;
  cameraMove?: "dolly_in" | "dolly_out" | "pedestal_rise" | "pan_left" | "pan_right";
}

export interface ViralReelProps {
  scenes: SceneData[];
  captions: CaptionBurst[];
  voiceoverAudioUrl?: string;
  ambientMusicUrl?: string;
  impactSfxUrl?: string;
  audioMix?: {
    voiceover: string; // "0dB"
    impact_sfx_on_cuts: string; // "-16dB"
    ambient_music: string; // "-22dB"
  };
}

export const ViralReel: React.FC<ViralReelProps> = ({
  scenes,
  captions,
  voiceoverAudioUrl,
  ambientMusicUrl,
  impactSfxUrl,
  audioMix = {
    voiceover: "0dB",
    impact_sfx_on_cuts: "-16dB",
    ambient_music: "-22dB",
  },
}) => {
  const { fps } = useVideoConfig();

  // Volume conversions:
  // 0dB = 1.0, -16dB = 0.1585, -22dB = 0.0794
  const voiceVolume = 1.0;
  const sfxVolume = 0.1585;
  const ambientVolume = 0.0794;

  let currentFrameOffset = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: "#000000" }}>
      {/* 1. Visual Scenes Sequence */}
      {scenes.map((scene, idx) => {
        const start = currentFrameOffset;
        currentFrameOffset += scene.durationInFrames;

        return (
          <Sequence
            key={idx}
            from={start}
            durationInFrames={scene.durationInFrames}
          >
            <SceneClip scene={scene} />
            {/* Impact SFX on cuts */}
            {impactSfxUrl && idx > 0 && (
              <Audio src={impactSfxUrl} volume={sfxVolume} />
            )}
          </Sequence>
        );
      })}

      {/* 2. Captions Layer */}
      <Captions bursts={captions} />

      {/* 3. Audio Layers */}
      {voiceoverAudioUrl && (
        <Audio src={voiceoverAudioUrl} volume={voiceVolume} />
      )}
      {ambientMusicUrl && (
        <Audio src={ambientMusicUrl} volume={ambientVolume} loop />
      )}
    </AbsoluteFill>
  );
};

const SceneClip: React.FC<{ scene: SceneData }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const scale = interpolate(
    frame,
    [0, scene.durationInFrames],
    [1.0, 1.15],
    { extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <Img
        src={scene.imageSrc}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale})`,
        }}
      />
    </AbsoluteFill>
  );
};
