import { Container, type ContainerProps } from "../../ui";

export type WidgetsProps = ContainerProps;

export const Widgets = ({ className, ...props }: WidgetsProps) => {
  return (
    <Container className={`${className || ""}`} {...props}>
      <div className="flex w-full h-full justify-center items-center">
        <h1 className="text-5xl">Widgets</h1>
      </div>
    </Container>
  );
};
