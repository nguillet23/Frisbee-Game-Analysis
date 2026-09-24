import { NavLink, Route, Routes } from "react-router-dom";
import Leaderboard from "./pages/Leaderboard.jsx";
import PlayerProfile from "./pages/PlayerProfile.jsx";
import Compare from "./pages/Compare.jsx";

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <span className="app-title">UFA Player Ratings</span>
        <nav>
          <NavLink to="/" end>
            Leaderboard
          </NavLink>
          <NavLink to="/compare">Compare</NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Leaderboard />} />
          <Route path="/players/:id" element={<PlayerProfile />} />
          <Route path="/compare" element={<Compare />} />
        </Routes>
      </main>
      <footer className="app-footer">
        <p>
          2026 UFA season · composite rating is a regression-learned, role-relative estimate — see{" "}
          <code>Plans/UFA_Analysis.md</code> for methodology and known limitations. Not an official UFA product.
        </p>
      </footer>
    </div>
  );
}
