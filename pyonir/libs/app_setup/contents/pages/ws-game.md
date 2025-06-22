@filter.jinja:- js
title: Websockets Game demo
menu.parent: /ws-demo
===
This page demonstrates the functionality of websockets using pycasso library and PhaserJS.

<dl>
    <dt>Your Gamer ID:</dt>
    <dd id="gamerid"></dd>
</dl>
<div id="game" style="text-align:center;"></div>
=== js
<script src="//cdn.jsdelivr.net/npm/phaser@3.55.2/dist/phaser.js"></script>
<script src="//raw.githubusercontent.com/photonstorm/phaser/v3.51.0/src/input/keyboard/KeyboardPlugin.js"></script>

<script>
var browser = "wsgame_{{request.browser}}";
var client_id = browser+Date.now() // Replace with user id
var domain = location.host
var protocol = location.protocol==='https:'?'wss':'ws';
gamerid.textContent = client_id;
var ws = null;
var WS_ROUTE = `${protocol}://${domain}/sample/ws?id=${client_id}`

var config = {
    type: Phaser.WEBGL,
    width: 800,
    height: 600,
    backgroundColor: '#2d2d2d',
    parent: 'game',
    physics: {
        default: 'arcade',
        arcade: {
            debug: true
        }
    },
    scene: {
        preload: preload,
        create: create,
        update: update
    }
};
var controls;
var cursors;
var player;
var guests = {};
var game = new Phaser.Game(config);
var World = null;
var logs = null;
var help = null;
class Player extends Phaser.Physics.Arcade.Sprite {
    id = null;
    constructor (x, y, id, texture='elephant')
    {
        super(World, x, y, texture);
        this.id = id ||  Math.random().toString(36).substring(7);
        World.physics.add.existing(this);
        this.scene.add.existing(this)
    }
}
function addGuests(id){
    console.log('addGuest', id)
    guest_player = new Player(560,280, id);
    guest_player.tint = 56789 * 0xffffff;
    guests[id] = guest_player
}
function preload ()
{
    World = this;
    this.load.setBaseURL('https://labs.phaser.io');
    this.load.image('ground', 'assets/tilemaps/tiles/kenny_ground_64x64.png');
    this.load.image('items', 'assets/tilemaps/tiles/kenny_items_64x64.png');
    this.load.image('platformer', 'assets/tilemaps/tiles/kenny_platformer_64x64.png');
    this.load.image('elephant', 'assets/sprites/elephant.png');
    this.load.tilemapTiledJSON('map', 'assets/tilemaps/maps/multi-tileset-v12.json');
}
function create ()
{
    var map = this.make.tilemap({ key: 'map' });
    var groundTiles = map.addTilesetImage('kenny_ground_64x64', 'ground');
    var itemTiles = map.addTilesetImage('kenny_items_64x64', 'items');
    var platformTiles = map.addTilesetImage('kenny_platformer_64x64', 'platformer');
    //  To use multiple tilesets in a single layer, pass them in an array like this:
    map.createLayer('Tile Layer 1', [ groundTiles, itemTiles, platformTiles ]);
    cursors = this.input.keyboard.createCursorKeys();
    this.cameras.main.setBounds(0, 0, map.widthInPixels, map.heightInPixels);
    var controlConfig = {
        camera: this.cameras.main,
        left: cursors.left,
        right: cursors.right,
        up: cursors.up,
        down: cursors.down,
        speed: 0.5
    };
    controls = new Phaser.Cameras.Controls.FixedKeyControl(controlConfig);

    help = this.add.text(16, 16, 'Arrow keys to scroll', {
        fontSize: '18px',
        padding: { x: 10, y: 5 },
        backgroundColor: '#000000',
        fill: '#ffffff'
    });
    logs = this.add.text(16, 46, 'logs here', {
        fontSize: '18px',
        position:{x:600},
        padding: { x: 10, y: 5 },
        backgroundColor: '#000000',
        fill: '#ffffff'
    });
    // player = new Player(400,300);
    help.setScrollFactor(0);
    cursors = this.input.keyboard.createCursorKeys();
    ws = new WebSocket(WS_ROUTE);
    ws.onopen = function(event){
        player = new Player(400,300, client_id);
    }
    ws.onerror = function(evt){
        console.log('ERROR', evt)
    }
    ws.onclose = function(evt){
        console.log('CLOSED', evt)
    }
    ws.onmessage = function(event) {
        // console.log('return data from server')
        var payload = typeof event.data==='string'? JSON.parse(event.data) : event.data;
        let action = payload.action
        console.log('onmessage', action)
        switch(action){
            case 'CONNECT_PLAYER':
                let plyrs = payload.data.filter((plyrId)=>{
                    return plyrId!==player.id && !guests[plyrId]
                    })
                console.log('connected player', payload.data, player.id, plyrs)
                plyrs.map(addGuests)
                break;
            case 'DISCONNECT_PLAYER':
                break;
            case 'PLAYER_MOVED':
                console.log(action, payload)
                let g = guests[payload.id];
                if(g){
                    g.x = payload.data[0];
                    g.y = payload.data[1];
                }
                break;
            default:
                console.log('default', action)
        }
    };

}
const DV = {
    MOVED_PLAYER:   2,
    CONNECT_PLAYER: 4,
    CONNECT_GUEST:  6,
}
function update (time, delta)
{
    if(!player){return}
    // controls.update(delta);
    player.setVelocity(0);
    is_moving = cursors.left.isDown||cursors.right.isDown||cursors.up.isDown||cursors.down.isDown;
    if (cursors.left.isDown)
    {
        player.setVelocityX(-300);
    }
    else if (cursors.right.isDown)
    {
        // console.log(player)
        player.setVelocityX(300);
    }

    if (cursors.up.isDown)
    {
        player.setVelocityY(-300);
    }
    else if (cursors.down.isDown)
    {
        player.setVelocityY(300);
    }
    if(is_moving){
        // ws.send("PLAYER_MOVED")
        ws.send(JSON.stringify({
            action: "PLAYER_MOVED",
            id: player.id,
            data: [player.x, player.y]
        }))
    }
}

</script>