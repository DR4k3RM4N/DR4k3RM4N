import React from "react";
import { Composition } from "remotion";
import { Video, PropsVideo, ejemplo } from "./Video";
import { Edu, EduProps, duracionEdu, ejemploEdu } from "./Edu";

// Una sola composición: el video base (tus cortes) + capas de motion graphics, todo por props (JSON).
// Render: npx remotion render src/index.ts Video salida.mp4 --props=props.json --public-dir=<carpeta del video base>
export const Raiz: React.FC = () => (
  <>
  <Composition
    id="Video"
    component={Video}
    defaultProps={ejemplo}
    fps={30}
    width={1080}
    height={1920}
    durationInFrames={300}
    calculateMetadata={({ props }: { props: PropsVideo }) => ({
      fps: props.fps || 30,
      width: props.ancho || 1080,
      height: props.alto || 1920,
      durationInFrames: Math.max(1, Math.round((props.duracion || 10) * (props.fps || 30))),
    })}
  />
  {/* 🎬 Edu IA: un video de YouTube completo (edu.json escrito por Claude); horizontal 1920x1080 */}
  <Composition
    id="Edu"
    component={Edu}
    defaultProps={ejemploEdu}
    fps={30}
    width={1920}
    height={1080}
    durationInFrames={120}
    calculateMetadata={({ props }: { props: EduProps }) => ({
      fps: props.fps || 30,
      width: props.ancho || 1920,
      height: props.alto || 1080,
      durationInFrames: Math.max(1, Math.round(duracionEdu(props) * (props.fps || 30))),
    })}
  />
  </>
);
