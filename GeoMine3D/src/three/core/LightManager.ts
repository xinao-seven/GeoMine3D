import * as THREE from 'three'
import {
    AMBIENT_LIGHT_COLOR,
    AMBIENT_LIGHT_INTENSITY,
    DIR_LIGHT_COLOR,
    DIR_LIGHT_INTENSITY,
} from '../constants'

export class LightManager {
    private ambientLight: THREE.AmbientLight
    private dirLight: THREE.DirectionalLight
    private hemiLight: THREE.HemisphereLight

    constructor(scene: THREE.Scene) {
        this.ambientLight = new THREE.AmbientLight(AMBIENT_LIGHT_COLOR, AMBIENT_LIGHT_INTENSITY)
        scene.add(this.ambientLight)

        this.dirLight = new THREE.DirectionalLight(DIR_LIGHT_COLOR, DIR_LIGHT_INTENSITY)
        this.dirLight.position.set(500, 800, 500)
        this.dirLight.castShadow = true
        scene.add(this.dirLight)

        this.hemiLight = new THREE.HemisphereLight(0x88bbff, 0x336644, 0.3)
        scene.add(this.hemiLight)
    }
}
