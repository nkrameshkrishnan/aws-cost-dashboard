import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface ProfileStore {
  selectedProfile: string
  availableProfiles: string[]
  setSelectedProfile: (profile: string) => void
  setAvailableProfiles: (profiles: string[]) => void
}

export const useProfileStore = create<ProfileStore>()(
  persist(
    (set) => ({
      selectedProfile: '',
      availableProfiles: [],
      setSelectedProfile: (profile: string) => set({ selectedProfile: profile }),
      setAvailableProfiles: (profiles: string[]) =>
        set({ availableProfiles: profiles }),
    }),
    {
      name: 'profile-storage',
    }
  )
)
