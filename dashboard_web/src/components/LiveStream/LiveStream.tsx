import { Container, type ContainerProps } from "../../ui";
import { Counter } from "../Counter";
import { Header } from "../Header";
import { VideoStream } from "../VideoStream";

export type LiveStreamProps = ContainerProps;

export const LiveStream = ({ className, ...props }: LiveStreamProps) => {
  return (
    <Container className={`flex flex-col ${className || ""}`} {...props}>
      <Header />
      <Counter />
      <VideoStream />
    </Container>
  );
};
