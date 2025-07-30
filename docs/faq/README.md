# FAQ

## Why tydom2mqtt?
Deltadore doesn't provide an official solution to make their hardware compatible with home automation solutions (Home-assistant...)

## How to reset my tydom password?
In october 2021, Deltadore has released a new version of its Tydom app (v4+) preventing to set or reset the Tydom password.

To set/reset your password, better download the previous version (v3+) which still allows to do it ([Aptoide link](https://tydom.fr.aptoide.com/app?store_name=aptoide-web&app_id=58618221)).

## How to prevent my tydom from communicating with Deltadore servers?
If you're concerned about your privacy, you can perform the following actions:
1. Configure you router to forbid your Tydom hub to access internet
2. Find your tydom local IP address and use it as `TYDOM_IP` value

## Why alarm motion sensor activity isn't reported?
- Alarm motion sensor activity isn't reported but when the alarm is fired then you get a cdata message so you can get the info (only when alarm is armed, pending and triggered).

## How to give a fixed IP to my device?
Depending on your internet box, your tydom may change IP when reconnecting and lose the connection with Home Assistant.
There is nothing in ([the official documentation](https://www.deltadore.fr/data/product_files/6700116/documents/notices/Install/fr/web_2705309_Rev2_Not_TYDOM_Home-EN_FR-rev02.pdf)) that explains this.
But your tydom has an accessible server where you can configure a fixed IP for it, look at the IPs on your router to find it then

![00](https://github.com/user-attachments/assets/8ef1edcd-aecf-4553-8ce1-3a27a1341f5a)
![01](https://github.com/user-attachments/assets/d8c22d3c-1f6f-436e-8050-0b24aa5489ab)
![02](https://github.com/user-attachments/assets/2c481a5f-51f7-4623-995b-9476baf9cdf4)
![03](https://github.com/user-attachments/assets/bc4dd270-c137-4ba7-8e62-c753f4834c30)

## How to make my Tydom completely offline?
Your Tydom works perfectly without any interaction with DELTADORE. You can of course still update the firmware with the app. But in terms of security and privacy, you'll gain a lot! To do this, simply block two domain names that allow data exchange:
- mediation.tydom.com
- mediation2.tydom.com

Using a DNS gateway like ([Pihole](https://github.com/pi-hole/pi-hole)), you can easily do this. And you'll have a functional Tydom locally :)

