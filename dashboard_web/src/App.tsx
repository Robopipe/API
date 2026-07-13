import { Toaster } from "sonner";
import { updateUserSettings } from "./api/userSettings";
import { ModelSelectModal } from "./components/Header/ModelSelectModal";
import { LiveStream } from "./components/LiveStream";
import { NoConfigError } from "./components/NoConfigError";
import {
  ProductCheckBanner,
  ProductSwitchModal,
} from "./components/ProductCheck";
import { Widgets } from "./components/Widgets";
import {
  AppStateProvider,
  CameraStreamProvider,
  SettingsLockProvider,
} from "./provider";
import { ResizablePanels } from "./ui";

function App() {
  if (!("DASHBOARD_CONFIG" in window)) {
    return <NoConfigError />;
  }

  const initialLeftPct =
    window.DASHBOARD_CONFIG.userSettings.videoPanelWidthPct ?? 40;

  return (
    <SettingsLockProvider>
      <AppStateProvider>
        <CameraStreamProvider>
          <Toaster theme="dark" position="bottom-right" />
          <main className="p-2 bg-gray-950 text-white w-full h-screen">
            <ResizablePanels
              className="w-full h-full"
              defaultLeftPct={initialLeftPct}
              onCommit={(pct) =>
                updateUserSettings({ videoPanelWidthPct: pct })
              }
              left={<LiveStream className="h-full" />}
              right={<Widgets className="h-full" />}
            />
          </main>
          {window.DASHBOARD_CONFIG.awaitingModel && <ModelSelectModal />}
          {window.DASHBOARD_CONFIG.productCheckEnabled && (
            <>
              <ProductCheckBanner />
              <ProductSwitchModal />
            </>
          )}
        </CameraStreamProvider>
      </AppStateProvider>
    </SettingsLockProvider>
  );
}

export default App;
