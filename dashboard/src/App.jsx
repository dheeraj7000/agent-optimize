import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Overview from './pages/Overview'
import Recommendations from './pages/Recommendations'
import Traces from './pages/Traces'
import Validation from './pages/Validation'
import Autopilot from './pages/Autopilot'
import Quickstart from './pages/Quickstart'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="recommendations" element={<Recommendations />} />
        <Route path="traces" element={<Traces />} />
        <Route path="validation" element={<Validation />} />
        <Route path="autopilot" element={<Autopilot />} />
        <Route path="quickstart" element={<Quickstart />} />
      </Route>
    </Routes>
  )
}
