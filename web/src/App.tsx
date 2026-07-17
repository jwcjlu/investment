import { BrowserRouter, Routes, Route, useParams } from 'react-router-dom'
import './App.css'

function Home() {
  return <h1>Home</h1>
}

function Module() {
  const params = useParams()
  const tag = params['*'] ?? ''
  return <h1>Module: {tag || '(none)'}</h1>
}

function Lesson() {
  const { id } = useParams()
  return <h1>Lesson: {id}</h1>
}

function Quiz() {
  return <h1>Quiz</h1>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/module/*" element={<Module />} />
        <Route path="/lesson/:id" element={<Lesson />} />
        <Route path="/quiz" element={<Quiz />} />
      </Routes>
    </BrowserRouter>
  )
}
