import { LoadingSpinner } from './LoadingSpinner'

interface LoadingPageProps {
  message?: string
}

export function LoadingPage({ message = 'Loading...' }: LoadingPageProps) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-modernGray-50 to-modernTeal-50">
      <div className="text-center">
        <LoadingSpinner size="xl" text={message} />
      </div>
    </div>
  )
}
