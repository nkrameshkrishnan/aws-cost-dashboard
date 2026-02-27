import { AlertCircle, Server, Database, Settings } from 'lucide-react'

interface SetupRequiredProps {
  error?: Error
  type: 'backend' | 'aws-accounts'
}

export function SetupRequired({ error, type }: SetupRequiredProps) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="max-w-2xl w-full bg-white rounded-lg shadow-lg p-8">
        <div className="flex items-center gap-3 mb-6">
          <AlertCircle className="h-8 w-8 text-amber-500" />
          <h1 className="text-2xl font-bold text-gray-900">
            {type === 'backend' ? 'Backend Not Configured' : 'AWS Account Setup Required'}
          </h1>
        </div>

        {type === 'backend' ? (
          <>
            <div className="mb-6">
              <p className="text-gray-600 mb-4">
                The AWS Cost Dashboard backend is not reachable. This could mean:
              </p>
              <ul className="list-disc list-inside space-y-2 text-gray-600 ml-4">
                <li>The backend API server is not running</li>
                <li>The API Gateway URL is not configured correctly</li>
                <li>Network connectivity issues</li>
              </ul>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
                <p className="text-sm font-medium text-red-800 mb-1">Error Details:</p>
                <p className="text-sm text-red-700 font-mono">{error.message}</p>
              </div>
            )}

            <div className="border-t pt-6 space-y-6">
              <div className="flex gap-3">
                <Server className="h-5 w-5 text-blue-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold text-gray-900 mb-2">Deploy Backend Infrastructure</h3>
                  <p className="text-sm text-gray-600 mb-2">
                    Deploy the backend using Terraform and AWS services:
                  </p>
                  <pre className="bg-gray-900 text-gray-100 p-3 rounded text-xs overflow-x-auto">
{`cd infrastructure/terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan`}
                  </pre>
                </div>
              </div>

              <div className="flex gap-3">
                <Database className="h-5 w-5 text-green-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold text-gray-900 mb-2">Get API Gateway URL</h3>
                  <p className="text-sm text-gray-600 mb-2">
                    After deployment, get the API Gateway URL:
                  </p>
                  <pre className="bg-gray-900 text-gray-100 p-3 rounded text-xs overflow-x-auto">
{`cd infrastructure/terraform
terraform output api_gateway_url`}
                  </pre>
                </div>
              </div>

              <div className="flex gap-3">
                <Settings className="h-5 w-5 text-purple-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold text-gray-900 mb-2">Update Frontend Configuration</h3>
                  <p className="text-sm text-gray-600 mb-2">
                    Update the frontend with the API Gateway URL and redeploy:
                  </p>
                  <pre className="bg-gray-900 text-gray-100 p-3 rounded text-xs overflow-x-auto">
{`export VITE_API_BASE_URL="https://your-api-url"
cd frontend
npm run build
# Deploy to GitHub Pages`}
                  </pre>
                </div>
              </div>
            </div>

            <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
              <p className="text-sm text-blue-800">
                <strong>📖 Documentation:</strong> For detailed deployment instructions, see{' '}
                <code className="bg-blue-100 px-1.5 py-0.5 rounded">IMPLEMENTATION_SUMMARY.md</code> and{' '}
                <code className="bg-blue-100 px-1.5 py-0.5 rounded">GITHUB_PAGES_DEPLOYMENT.md</code>
              </p>
            </div>
          </>
        ) : (
          <>
            <div className="mb-6">
              <p className="text-gray-600 mb-4">
                No AWS accounts have been configured yet. To start monitoring AWS costs, you need to:
              </p>
            </div>

            <div className="border-t pt-6 space-y-6">
              <div className="flex gap-3">
                <Settings className="h-5 w-5 text-blue-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold text-gray-900 mb-2">1. Configure AWS Credentials</h3>
                  <p className="text-sm text-gray-600 mb-2">
                    Set up AWS credentials with Cost Explorer permissions:
                  </p>
                  <pre className="bg-gray-900 text-gray-100 p-3 rounded text-xs overflow-x-auto">
{`aws configure --profile my-account
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Enter your default region`}
                  </pre>
                </div>
              </div>

              <div className="flex gap-3">
                <Database className="h-5 w-5 text-green-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold text-gray-900 mb-2">2. Add Account via API</h3>
                  <p className="text-sm text-gray-600 mb-2">
                    Once the backend is running, add your AWS account through the AWS Accounts page.
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
              <p className="text-sm text-blue-800">
                <strong>📖 Documentation:</strong> For IAM permissions required, see{' '}
                <code className="bg-blue-100 px-1.5 py-0.5 rounded">IAM_SETUP_GUIDE.md</code> and{' '}
                <code className="bg-blue-100 px-1.5 py-0.5 rounded">AWS_ACCOUNTS_SETUP.md</code>
              </p>
            </div>
          </>
        )}

        <div className="mt-8 flex gap-3">
          <button
            onClick={() => window.location.reload()}
            className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
          >
            Retry Connection
          </button>
          <a
            href="https://dsgithub.trendmicro.com/rameshkrishnan-narashimankrishnamurthy/aws-cost-dashboard"
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition-colors text-center"
          >
            View Documentation
          </a>
        </div>
      </div>
    </div>
  )
}
