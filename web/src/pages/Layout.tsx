import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

interface LayoutProps {
  children: ReactNode
  breadcrumb?: ReactNode
}

export default function Layout({ children, breadcrumb }: LayoutProps) {
  return (
    <div className="site">
      <header className="site-header">
        <Link className="brand" to="/">
          投资学习路径
        </Link>
      </header>
      <main className="content">
        {breadcrumb && <nav className="breadcrumb">{breadcrumb}</nav>}
        {children}
      </main>
    </div>
  )
}

export function LoadingBlock({ label = '加载中…' }: { label?: string }) {
  return <p className="hint">{label}</p>
}

export function ErrorBlock({ message }: { message: string }) {
  return <p className="error-text">出错了：{message}</p>
}
