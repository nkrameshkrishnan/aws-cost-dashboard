import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useProfileStore } from '@/store/profileStore'
import { awsAccountsApi } from '@/api/awsAccounts'

export function ProfileSelector() {
  const { selectedProfile, setSelectedProfile, availableProfiles, setAvailableProfiles } = useProfileStore()
  const initializedRef = useRef(false)

  // Fetch AWS accounts from database
  const { data: accounts, isLoading } = useQuery({
    queryKey: ['awsAccounts'],
    queryFn: () => awsAccountsApi.list(true), // Only active accounts
  })

  // Update available profiles when accounts are loaded
  useEffect(() => {
    if (!accounts || accounts.length === 0) return

    const profileNames = accounts.map(acc => acc.name)

    // Only update if profiles have actually changed
    const profilesChanged =
      profileNames.length !== availableProfiles.length ||
      profileNames.some((name, index) => name !== availableProfiles[index])

    if (profilesChanged) {
      setAvailableProfiles(profileNames)
    }

    // Only set default profile once on initial load
    if (!initializedRef.current && (!selectedProfile || !profileNames.includes(selectedProfile))) {
      setSelectedProfile(profileNames[0])
      initializedRef.current = true
    }
  }, [accounts, availableProfiles, selectedProfile, setAvailableProfiles, setSelectedProfile])

  const handleProfileChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedProfile(event.target.value)
  }

  if (isLoading) {
    return (
      <div className="text-sm text-gray-500">Loading accounts...</div>
    )
  }

  if (!accounts || accounts.length === 0) {
    return (
      <div className="text-sm text-amber-600">
        No AWS accounts configured. <a href="/aws-accounts" className="underline">Add one</a>
      </div>
    )
  }

  return (
    <div className="flex items-center space-x-2">
      <label htmlFor="profile-select" className="text-sm font-medium text-gray-700">
        AWS Account:
      </label>
      <select
        id="profile-select"
        value={selectedProfile}
        onChange={handleProfileChange}
        className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
      >
        {accounts.map((account) => (
          <option key={account.id} value={account.name}>
            {account.name}
          </option>
        ))}
      </select>
    </div>
  )
}
