import React from "react";
import { interpolate, useCurrentFrame } from "remotion";

export interface CaptionWord {
  word: string;
  startFrame: number;
  endFrame: number;
  isHighlight?: boolean;
}

export interface CaptionBurst {
  words: CaptionWord[];
  startFrame: number;
  endFrame: number;
}

export const Captions: React.FC<{
  bursts: CaptionBurst[];
}> = ({ bursts }) => {
  const frame = useCurrentFrame();
  const currentBurst = bursts.find(
    (b) => frame >= b.startFrame && frame <= b.endFrame
  );

  if (!currentBurst) {
    return null;
  }

  return (
    <div
      style={{
        position: "absolute",
        top: 1200,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        textAlign: "center",
        zIndex: 50,
      }}
    >
      <div
        style={{
          display: "flex",
          gap: 16,
          justifyContent: "center",
          flexWrap: "wrap",
          padding: "12px 32px",
          maxWidth: 960,
        }}
      >
        {currentBurst.words.map((w, idx) => {
          const isActive = frame >= w.startFrame && frame <= w.endFrame;
          const color = isActive || w.isHighlight ? "#FFE500" : "#FFFFFF";
          return (
            <span
              key={idx}
              style={{
                fontFamily: "Impact, sans-serif",
                fontSize: 64, // 48pt font in pixel scale
                textTransform: "uppercase",
                color,
                textShadow:
                  "4px 4px 0px #000000, -4px -4px 0px #000000, 4px -4px 0px #000000, -4px 4px 0px #000000, 0px 6px 12px rgba(0,0,0,0.9)",
                letterSpacing: 2,
              }}
            >
              {w.word}
            </span>
          );
        })}
      </div>
    </div>
  );
};
