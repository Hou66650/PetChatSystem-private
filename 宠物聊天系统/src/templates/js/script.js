function createCherryBlossoms() {
    var cherryBlossom = $('<div class="cherry-blossoms"></div>');
    cherryBlossom.css({
        top: Math.random() * $(window).height(),
        left: Math.random() * $(window).width(),
        animationDuration: (Math.random() * 3 + 4) + 's',
        animationDelay: -(Math.random() * 2) + 's',
    });
    $('body').append(cherryBlossom);
}

for(var i = 0; i < 80; i++) {
    createCherryBlossoms();
}