import { Toaster } from "sonner";
import { LiveStream } from "./components/LiveStream";
import { NoConfigError } from "./components/NoConfigError";
import { Widgets } from "./components/Widgets";
import { AppStateProvider, CameraStreamProvider } from "./provider";
import { ResizablePanels } from "./ui";

function App() {
  if (!("DASHBOARD_CONFIG" in window)) {
    return <NoConfigError />;
  }

  return (
    <AppStateProvider>
      <CameraStreamProvider>
        <Toaster theme="dark" position="bottom-right" />
        <main className="p-2 bg-gray-950 text-white w-full h-screen">
          <ResizablePanels
            className="w-full h-full"
            defaultLeftPct={40}
            left={<LiveStream className="h-full" />}
            right={<Widgets className="h-full" />}
          />
        </main>
      </CameraStreamProvider>
    </AppStateProvider>
  );
}

export default App;
