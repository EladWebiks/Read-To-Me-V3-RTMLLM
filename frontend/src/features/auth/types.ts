export type User = {
  id: string
  username: string
  email: string | null
  picture_url: string | null
  is_admin: boolean
  membership: string
  created_at: string
}

export type MeResponse = {
  user: User
  membership_label: string
}
