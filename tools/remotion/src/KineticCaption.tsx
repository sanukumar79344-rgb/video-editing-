import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

export const KineticCaption: React.FC<{words: string[]}> = ({words}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const per = 18;
  const active = Math.min(words.length - 1, Math.floor(frame / per));
  return (
    <AbsoluteFill style={{backgroundColor: '#0b0b0f', justifyContent: 'center', alignItems: 'center'}}>
      <div style={{display: 'flex', gap: 24, flexWrap: 'wrap', justifyContent: 'center', padding: 60}}>
        {words.map((w, i) => {
          const s = spring({frame: frame - i * per, fps, config: {damping: 14}});
          const on = i === active;
          return (
            <span key={i} style={{
              fontFamily: 'Montserrat, sans-serif', fontWeight: 800, fontSize: 96,
              color: on ? '#FFD400' : '#fff',
              transform: `scale(${interpolate(s, [0, 1], [0.7, on ? 1.1 : 1])})`,
              opacity: interpolate(s, [0, 1], [0, 1]),
              textShadow: '0 6px 24px rgba(0,0,0,.6)',
            }}>{w}</span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
