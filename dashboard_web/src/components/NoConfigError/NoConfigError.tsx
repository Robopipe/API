const RobopipeLogo = () => (
  <svg
    width="160"
    height="32"
    viewBox="0 0 160 32"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M12.5 4C8.08 4 4.5 7.58 4.5 12s3.58 8 8 8c1.57 0 3.03-.46 4.26-1.24l4.49 4.49a1.5 1.5 0 0 0 2.12-2.12l-4.49-4.49A7.96 7.96 0 0 0 20.5 12c0-4.42-3.58-8-8-8Zm0 3a5 5 0 1 1 0 10 5 5 0 0 1 0-10Z"
      fill="#43C47D"
    />
    <text
      x="32"
      y="21"
      fontFamily="system-ui, -apple-system, sans-serif"
      fontSize="18"
      fontWeight="600"
      fill="white"
      letterSpacing="0.5"
    >
      robopipe
    </text>
  </svg>
);

const AlertIcon = () => (
  <svg
    width="48"
    height="48"
    viewBox="0 0 24 24"
    fill="none"
    stroke="#43C47D"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);

export const NoConfigError = () => {
  return (
    <div
      className="flex min-h-screen flex-col items-center justify-between px-6 py-10"
      style={{
        background:
          "linear-gradient(180deg, rgba(67, 196, 125, 0.15) 0%, rgba(0, 0, 0, 0) 40%), #0f0f18",
      }}
    >
      {/* Logo */}
      <div className="flex items-center justify-center">
        <RobopipeLogo />
      </div>

      {/* Main content */}
      <div className="flex flex-col items-center gap-6 text-center">
        {/* Icon */}
        <div className="flex h-24 w-24 items-center justify-center rounded-full border border-emerald-500/30 bg-emerald-500/5">
          <AlertIcon />
        </div>

        {/* Heading */}
        <h1 className="text-4xl font-semibold leading-tight text-white">
          Configuration
          <br />
          not found
        </h1>

        {/* Description */}
        <div className="flex max-w-md flex-col gap-4">
          <p className="text-sm leading-relaxed text-text-white-secondary">
            We're sorry, but the dashboard configuration could not be loaded.
            Please make sure the device is properly set up and the configuration
            has been provided.
          </p>
          <p className="text-sm text-text-white-secondary">
            If the issue persists, try restarting the device or contact support.
          </p>
        </div>
      </div>

      {/* Footer */}
      <footer className="flex items-center gap-3 text-xs text-text-white-disabled">
        <span>Powered by Robopipe</span>
        <span className="text-text-white-disabled/40">|</span>
        <span>&copy; All rights reserved</span>
      </footer>
    </div>
  );
};
