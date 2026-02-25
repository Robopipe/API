function App() {
  if (!("DASHBOARD_CONFIG" in window)) {
    console.warn("DASHBOARD_CONFIG is not defined on window");
  }

  return (
    <div>
      <div>Robopipe Dashboard</div>
    </div>
  );
}

export default App;
