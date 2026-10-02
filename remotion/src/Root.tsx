import React from "react";
import { Composition } from "remotion";
import { ViralReel } from "./ViralReel";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="ViralReel"
      component={ViralReel}
      durationInFrames={780} // 26 seconds at 30 fps (24-28s range)
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        scenes: [],
        captions: [],
        audioMix: {
          voiceover: "0dB",
          impact_sfx_on_cuts: "-16dB",
          ambient_music: "-22dB",
        },
      }}
    />
  );
};
