export interface ContainerProps {
  children?: React.ReactNode;
}

export const Container = ({ children }: ContainerProps) => {
  return <div className="bg-gray-900 p-3">{children}</div>;
};
