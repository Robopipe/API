export interface ContainerProps extends React.HTMLAttributes<HTMLDivElement> {
  children?: React.ReactNode;
}

export const Container = ({
  children,
  className = "",
  ...props
}: ContainerProps) => {
  return (
    <div className={`bg-gray-900 p-3 rounded-2xl ${className}`} {...props}>
      {children}
    </div>
  );
};
