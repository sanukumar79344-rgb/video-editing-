import {Composition} from 'remotion';
import {KineticCaption} from './KineticCaption';

export const RemotionRoot: React.FC = () => (
  <Composition
    id="KineticCaption"
    component={KineticCaption}
    durationInFrames={75}
    fps={25}
    width={1080}
    height={1920}
    defaultProps={{words: ['KYA', 'BAAT', 'HAI', 'YAAR']}}
  />
);
