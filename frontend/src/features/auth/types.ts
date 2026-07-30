export type User = {
  id: string
  username: string
  email: string | null
  picture_url: string | null
  role: string
  created_at: string
}

export type MeResponse = {
  user: User
}
