import { RateVolumeControls } from './RateVolumeControls'

type Props = {
  rate: number
  volume: number
  onRate: (rate: number) => void
  onVolume: (volume: number) => void
}

/** Expanded reader playback row: speed and volume only. */
export function PlayerControls(props: Props) {
  return <RateVolumeControls {...props} />
}
