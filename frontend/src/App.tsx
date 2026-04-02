import { BrowserRouter, Routes, Route } from "react-router-dom";
import CustomerCallPage from "./pages/CustomerCallPage";
import DashboardPage from "./pages/DashboardPage";
import "./index.css";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<CustomerCallPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
