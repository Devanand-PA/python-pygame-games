### Save Data Form :
import pathlib
import json
'''
{ 
    "user" : "User Name",
    "campaign" : "Campaign Name"
    "scenario" : "Scenario Name"
    "enemies" : [
    { "type" : "flyer-001",
      "position" : [100,100],
      "HP total" : 100,
      "HP left" : 50 
      },
      ....
      ],
    "towers" : [
    ....
    ],

    "Base" : {

    "HP Total" : ..,
    }

    ]

}
'''

def save_game(savedata) :
    savedir = pathlib.Path.home() / "Documents"  / "Saves" / "bigtower" / savedata["user"] / savedata["campaign"] / savedata["scenario"]
    if not savedir.exists() :
        savedir.mkdir(parents=True)
    if savedir.isdir() :
        k = 0   
        for save in savedir.iterdir() :
            if str(save).endswith(".save") :
                save_num = int(str(save).rstrip(".save"))
                if save_num > k :
                    k = save_num
        savefile = savedir / f"{k}.save"

        with open( str(savefile.resolve) , 'w' ) as File :
            json.dump(savedata,File)



def load_game(user, campaign, scenario) :
    savedir =     savedir = pathlib.Path.home() / "Documents"  / "Saves" / "bigtower" / user / campaign / scenario
    if not savedir.exists() :
        savedir.mkdir(parents=True)
    if savedir.isdir() :
        k = 0   
        for save in savedir.iterdir() :
            if str(save).endswith(".save") :
                save_num = int(str(save).rstrip(".save"))
                if save_num > k :
                    k = save_num
        savefile = savedir / f"{k}.save"
        with open( str(savefile.resolve)) as File :
            savedata = json.load(File)
        return savedata


def list_users() :
    gamesave_dir =     savedir = pathlib.Path.home() / "Documents"  / "Saves" / "bigtower"
    enlisted_users = []
    if not gamesave_dir.exists() :
        gamesave_dir.mkdir(parents=True)
    for i in gamesave_dir.iterdir() :
        if ( gamesave_dir / str(i) ).is_dir() :
            enlisted_users.append(str(i.name))
    return enlisted_users or []


def create_user(user : str) :
    gamesave_dir =     savedir = pathlib.Path.home() / "Documents"  / "Saves" / "bigtower"
    if not gamesave_dir.exists() :
        gamesave_dir.mkdir(parents=True)
   
    user_dir = gamesave_dir / user
    
    if not user_dir.exists() :
        user_dir.mkdir(parents=True)






