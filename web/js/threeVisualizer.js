import * as THREE from 'three';
import { api } from '../../../scripts/api.js';

import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TextGeometry } from 'three/addons/geometries/TextGeometry.js';
import { FontLoader } from 'three/addons/loaders/FontLoader.js'; // Import FontLoader
import * as dat from 'three/addons/libs/lil-gui.module.min'


const visualizer = document.getElementById("visualizer");
const container = document.getElementById("container");
const progressDialog = document.getElementById("progress-dialog");
const progressIndicator = document.getElementById("progress-indicator");

const gui = new dat.GUI({ width: 150 });
const fov = 75;
const params = {
    showText: true,
    fov: fov
  };
  
gui.add(params, 'showText').name('Show Text').onChange((value) => {
textMesh.visible = value;
});

gui.add(params, 'fov', 10, 120).name('Zoom').step(0.1).onChange(function () {
    camera.fov = params.fov;
    camera.updateProjectionMatrix();
});

const renderer = new THREE.WebGLRenderer({ antialias: true, extensions: {
    derivatives: true
}});
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(window.innerWidth, window.innerHeight);
container.appendChild(renderer.domElement);

const pmremGenerator = new THREE.PMREMGenerator(renderer);

// scene
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x000000);

const ambientLight = new THREE.AmbientLight(0xffffff);


const camera = new THREE.PerspectiveCamera(fov, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 0, 5);

const pointLight = new THREE.PointLight(0xffffff, 15);
camera.add(pointLight);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0, 0);
controls.update();
controls.enablePan = true;
controls.enableDamping = true;

// Handle window resize event
window.onresize = function () {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();

    renderer.setSize(window.innerWidth, window.innerHeight);
};

var lastHdriImage = "";
var lastDreamInterpretation = "";
var needUpdate = false;

function frameUpdate() {
    var hdriImage = visualizer.getAttribute("hdri_image");
    var dreamInterpretation = visualizer.getAttribute("dream_interpretation");
    if (textMesh) {
        // Make the text face the camera
        textMesh.lookAt(camera.position);
    }
    if (hdriImage == lastHdriImage && dreamInterpretation == lastDreamInterpretation) {
        if (needUpdate) {
            controls.update();
            renderer.render(scene, camera);
        }
        requestAnimationFrame(frameUpdate);
    
    } else {
        needUpdate = false;
        scene.clear();
        progressDialog.open = true;
        lastHdriImage = hdriImage;
        lastDreamInterpretation = dreamInterpretation;
        main(JSON.parse(lastHdriImage), lastDreamInterpretation);
    }
}

let textMesh;
async function main(hdriImageParams, dreamInterpretation) {
    let hdriTexture;
    console.log(hdriImageParams, dreamInterpretation);
    if (hdriImageParams?.filename) {
        const hdriImageUrl = api.apiURL('/view?' + new URLSearchParams(hdriImageParams)).replace(/extensions.*\//, "");
        const hdriImageExt = hdriImageParams.filename.slice(hdriImageParams.filename.lastIndexOf(".") + 1);
        const hdriLoader = new THREE.TextureLoader();
        hdriTexture = await hdriLoader.loadAsync(hdriImageUrl);
        console.log(hdriTexture);
        hdriTexture.mapping = THREE.EquirectangularReflectionMapping;
        hdriTexture.colorSpace = THREE.SRGBColorSpace;
    }

    if (hdriTexture) {
        scene.environment = hdriTexture;
        scene.background = hdriTexture;
    }
   
    // Use the imported FontLoader here
    const fontLoader = new FontLoader();
    fontLoader.load('https://threejs.org/examples/fonts/helvetiker_regular.typeface.json', function (font) {
    // Function to split the text into lines after every 10 words
    function splitTextIntoLines(text, wordsPerLine) {
        const words = text.replace(/"\s*"/g, '').split(' ');
        let result = '';

        for (let i = 0; i < words.length; i += wordsPerLine) {
            const line = words.slice(i, i + wordsPerLine).join(' ');
            result += i + wordsPerLine < words.length ? line + '\n' : line;
        }

        return result;
    }

    // Using the function to process your text
    const processedText = splitTextIntoLines(dreamInterpretation, 10);
    
    const textGeometry = new TextGeometry(processedText, {
        font: font,
        size: 0.5,
        height: 0.1,
        curveSegments: 12
    });

    textGeometry.computeBoundingBox();

    const textWidth = textGeometry.boundingBox.max.x - textGeometry.boundingBox.min.x;
    const textHeight = textGeometry.boundingBox.max.y - textGeometry.boundingBox.min.y;

    const textMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff });
    textMesh = new THREE.Mesh(textGeometry, textMaterial);

    // Center the text mesh
    textMesh.position.x = -0.5 * textWidth;
    textMesh.position.y = -0.5 * textHeight;
    textMesh.position.z = 0;

    scene.add(textMesh);
    });
    needUpdate = true;

    // Assume ambientLight and camera have been defined somewhere above this snippet
    scene.add(ambientLight);
    scene.add(camera);

    progressDialog.close();

    frameUpdate();

    }

main();